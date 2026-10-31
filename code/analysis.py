#!/usr/bin/env python3
"""
Review 3 - Stage 4 analysis (Statistician)
SOFTWARE FALLBACK DISCLOSURE:
  The pre-specified primary route was R metafor::rma.glmm(measure="PLO").
  R is not installed on this machine (R/Rscript not found), apt-get update
  timed out, and pip install of statsmodels was blocked by an egress
  HTTP 403 from the package proxy. Therefore this analysis uses the
  disclosed fallback: a hand-written random-effects GLMM with logit link
  for binomial proportions, fitted by maximum likelihood in Python
  (scipy.optimize), integrating the normal random effect with
  21-point adaptive Gauss-Hermite quadrature (per-unit posterior-mode
  centring and curvature scaling; validated against scipy.integrate.quad
  to 6 decimal places on the headline pool - a first non-adaptive
  quadrature attempt was caught by this validation, discarded, and is
  logged in the hand-check log). This is the same statistical model
  as rma.glmm measure="PLO" (binomial likelihood, normal random effect
  on the logit scale, ML estimator). Every output is labelled with the
  actual software used. No continuity correction, no arcsine transform.
  Boundary counts (x=0 or x=n) are retained; the binomial likelihood
  handles them.

Model:
  x_i ~ Binomial(n_i, p_i); logit(p_i) = mu + u_i; u_i ~ N(0, tau^2)
Prediction interval (k>=3): on logit scale,
  mu +/- 1.96 * sqrt(tau^2 + SE(mu)^2), back-transformed.
I-squared (GLMM analogue, footnoted in outputs):
  I2 = tau^2 / (tau^2 + v_typ), v_typ = Higgins-Thompson typical
  within-unit sampling variance on the logit scale,
  v_typ = ((k-1) * sum(w)) / ((sum w)^2 - sum(w^2)), w_i = 1/v_i,
  v_i = 1 / (n_i * p_i * (1-p_i)) with p_i smoothed as (x_i+0.5)/(n_i+1)
  ONLY for this variance/I2 calculation (never for the fit itself).
Hartung-Knapp: NOT applied to GLMM headline estimates, per analysis
  plan section 4. The plan's HK sensitivity is specified for the
  primary pool only; the primary pool does not exist (single unit),
  so no HK sensitivity is fittable. This is recorded in the output.
Subgroup interaction: GLMM meta-regression with a categorical
  moderator (separate mu per level, common tau^2), tested by a
  likelihood-ratio test against the no-moderator GLMM (chi-square,
  df = levels-1). No subgroup claim is made without this test.
"""
import csv, json, math, os, sys
import numpy as np
from scipy import optimize, stats
from scipy.special import expit, gammaln

BASE = os.path.expanduser("~/workspace/publications/weekly-series/meta-analysis-clinical-summarization-errors/review3")
SETTLED = os.path.join(BASE, "stage3-extraction/extraction-settled.csv")
OUTDIR = os.path.join(BASE, "stage4-analysis")
FIGDIR = os.path.join(OUTDIR, "figures")
os.makedirs(FIGDIR, exist_ok=True)

# Adaptive Gauss-Hermite quadrature: physicists' hermgauss nodes/weights
GH_T, GH_W = np.polynomial.hermite.hermgauss(21)  # for integral of exp(-t^2) g(t)

SHORT = {  # short study labels: first author, year, arm discriminator
 "CC2-03-1": ("Song 2025", "Ko-Llama3"),
 "R0047-1": ("Tung 2024", "GPT-4"),
 "R0047-2": ("Tung 2024", "human"),
 "R0123-1": ("Ganzinger 2025", "LLaMA3"),
 "R0144-1": ("Watcharasarn 2025", "GPT-4o"),
 "R0167-1": ("Williams 2025", "GPT-4"),
 "R0167-2": ("Williams 2025", "GPT-3.5"),
 "R0301-1": ("Park 2026", "GPT-4o initial"),
 "R0301-2": ("Park 2026", "GPT-4o pilot"),
 "R0354-1": ("Dhanda 2026", "llama3.2 A"),
 "R0354-2": ("Dhanda 2026", "llama3.2 B"),
 "R0354-3": ("Dhanda 2026", "gemma3 A"),
 "R0354-4": ("Dhanda 2026", "gemma3 B"),
 "R0354-5": ("Dhanda 2026", "qwen2.5 A"),
 "R0354-6": ("Dhanda 2026", "qwen2.5 B"),
 "R0354-7": ("Dhanda 2026", "gemma2 A"),
 "R0354-8": ("Dhanda 2026", "gemma2 B"),
 "R0370-1": ("Jolin-Rodrigo 2026", "gemini-2.5-flash"),
 "R0370-2": ("Jolin-Rodrigo 2026", "gpt-oss-20b"),
 "R0391-1": ("Nakano 2026", "Ubie AI"),
 "R0429-1": ("Bodanki 2026", "Epic GPT-4"),
 "R0438-1": ("Grolleau 2026", "Gemini 2.5 Pro"),
}

def load():
    with open(SETTLED, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for c in ["n_assessed","n_clinically_significant","n_any_error","n_omission",
                  "n_fabrication","n_inaccuracy","n_harm_moderate","total_errors"]:
            r[c] = int(r[c]) if r[c].strip() != "" else None
        for c in ["errors_per_summary_mean","errors_per_summary_sd"]:
            r[c] = float(r[c]) if r[c].strip() != "" else None
        r["preprint"] = r["preprint"].strip().lower() == "yes"
        r["label"] = f"{SHORT[r['arm_id']][0]}, {SHORT[r['arm_id']][1]}"
    return rows

ROWS = load()
LLM = [r for r in ROWS if r["arm_type"] == "llm"]

def units(field):
    return [r for r in LLM if r[field] is not None]

# ---------- GLMM fitting ----------
def negll(params, xs, ns, design):
    """design: (k x m) matrix mapping unit -> mu column. params = [mus..., log_tau].
    Marginal likelihood per unit by 21-point adaptive Gauss-Hermite quadrature:
    nodes centred on each unit's posterior mode (Newton, vectorised) and scaled
    by its posterior curvature."""
    mus = design @ params[:-1]
    tau = max(math.exp(params[-1]), 1e-8)
    # posterior mode of u_i: maximise x*log(p)+(n-x)*log(1-p)-u^2/(2 tau^2)
    u = np.clip(np.log((xs+0.5)/(ns-xs+0.5)) - mus, -12, 12)
    for _ in range(60):
        p = expit(mus+u)
        grad = xs - ns*p - u/tau**2
        hess = -ns*p*(1-p) - 1/tau**2
        step = grad/hess
        u = u - step
        if np.max(np.abs(step)) < 1e-11:
            break
    p = expit(mus+u)
    s = 1.0/np.sqrt(ns*p*(1-p) + 1/tau**2)          # posterior scale per unit
    U = u[:, None] + math.sqrt(2)*s[:, None]*GH_T[None, :]   # k x Q nodes for u
    pp = expit(mus[:, None] + U)
    lc = (gammaln(ns+1)-gammaln(xs+1)-gammaln(ns-xs+1))[:, None]
    h = (lc + xs[:, None]*np.log(np.clip(pp, 1e-300, 1))
         + (ns-xs)[:, None]*np.log(np.clip(1-pp, 1e-300, 1))
         - 0.5*(U/tau)**2 - math.log(tau) - 0.5*math.log(2*math.pi))
    integ = math.sqrt(2)*s*(GH_W[None, :]*np.exp(h + GH_T[None, :]**2)).sum(axis=1)
    return -float(np.log(np.clip(integ, 1e-300, None)).sum())

def hess_se(fun, params, args):
    """SEs from inverse numerical Hessian (central differences)."""
    p = np.array(params, dtype=float); m = len(p)
    h = np.array([1e-4]*m); f0 = fun(p, *args)
    H = np.zeros((m, m))
    for i in range(m):
        for j in range(m):
            ei = np.zeros(m); ei[i] = h[i]
            ej = np.zeros(m); ej[j] = h[j]
            H[i, j] = (fun(p+ei+ej, *args) - fun(p+ei-ej, *args)
                       - fun(p-ei+ej, *args) + fun(p-ei-ej, *args)) / (4*h[i]*h[j])
    try:
        cov = np.linalg.inv(H)
        se = np.sqrt(np.abs(np.diag(cov)))
    except np.linalg.LinAlgError:
        se = np.full(m, np.nan)
    return se

def fit(xs, ns, levels=None):
    """Fit GLMM. levels=None -> single mu. levels=array of level index per unit -> moderator model.
       Returns dict with mu(s), se(s), tau2, loglik, convergence."""
    xs = np.asarray(xs, float); ns = np.asarray(ns, float); k = len(xs)
    if levels is None:
        design = np.ones((k, 1)); m = 1
    else:
        lev = np.asarray(levels); m = int(lev.max())+1
        design = np.zeros((k, m)); design[np.arange(k), lev] = 1.0
    crude = xs.sum()/ns.sum()
    mu0 = math.log(crude/(1-crude)) if 0 < crude < 1 else 0.0
    best = None
    for ltau0 in (-1.0, 0.0, 1.0):
        x0 = np.array([mu0]*m + [ltau0])
        res = optimize.minimize(negll, x0, args=(xs, ns, design), method="Nelder-Mead",
                                options=dict(maxiter=20000, xatol=1e-8, fatol=1e-8))
        res2 = optimize.minimize(negll, res.x, args=(xs, ns, design), method="BFGS",
                                 options=dict(maxiter=5000))
        cand = res2 if res2.fun <= res.fun else res
        if best is None or cand.fun < best.fun:
            best = cand
    se = hess_se(negll, best.x, (xs, ns, design))
    tau2 = float(math.exp(best.x[-1])**2)
    out = dict(mus=[float(v) for v in best.x[:-1]], ses=[float(v) for v in se[:-1]],
               tau2=tau2, tau=math.sqrt(tau2), loglik=-float(best.fun),
               converged=bool(best.success), optimizer_message=str(best.message), k=k)
    if m == 1:
        mu, s = out["mus"][0], out["ses"][0]
        out.update(pooled=float(expit(mu)),
                   ci_lo=float(expit(mu-1.96*s)), ci_hi=float(expit(mu+1.96*s)),
                   mu=mu, se=s)
        if k >= 3:
            half = 1.96*math.sqrt(tau2 + s*s)
            out.update(pi_lo=float(expit(mu-half)), pi_hi=float(expit(mu+half)))
        else:
            out.update(pi_lo=None, pi_hi=None)
        # I2 GLMM analogue
        ps = (xs+0.5)/(ns+1.0)
        v = 1.0/(ns*ps*(1-ps)); w = 1.0/v
        if k > 1:
            vtyp = ((k-1)*w.sum()) / (w.sum()**2 - (w**2).sum())
            out["I2"] = float(tau2/(tau2+vtyp)*100) if (tau2+vtyp) > 0 else 0.0
            out["v_typ"] = float(vtyp)
        else:
            out["I2"] = None; out["v_typ"] = None
    return out

def cp_ci(x, n, alpha=0.05):
    lo = 0.0 if x == 0 else float(stats.beta.ppf(alpha/2, x, n-x+1))
    hi = 1.0 if x == n else float(stats.beta.ppf(1-alpha/2, x+1, n-x))
    return lo, hi

RESULTS = {}
def do_pool(name, field, unit_rows=None):
    us = unit_rows if unit_rows is not None else units(field)
    xs = [r[field] for r in us]; ns = [r["n_assessed"] for r in us]
    f = fit(xs, ns)
    f.update(name=name, field=field, units=us, total_x=int(sum(xs)), total_n=int(sum(ns)),
             n_units=len(us), n_studies=len(set(r["study_id"] for r in us)),
             crude=float(sum(xs)/sum(ns)))
    RESULTS[name] = f
    return f

# ---------- Main pools ----------
pool_any   = do_pool("any_error_supplementary", "n_any_error")
pool_omit  = do_pool("omission", "n_omission")
pool_fab   = do_pool("fabrication_addition", "n_fabrication")
pool_inacc = do_pool("inaccuracy", "n_inaccuracy")

# Omission sensitivity excluding R0354 (risk-fact-specific counts)
omit_no354 = [r for r in units("n_omission") if r["study_id"] != "R0354"]
pool_omit_no354 = do_pool("omission_excl_R0354", "n_omission", omit_no354)

# ---------- Sensitivities ----------
# S1 analogue: units from studies with any explicit severity or harm grading.
# Rule (stated in output): study applied an explicit severity, harm, major or
# critical grading, as evidenced in the settled file (definition_status =
# clinically_significant_defined, or harm/severity grading recorded in
# derived_notes). Studies meeting the rule: R0167 (harm graded per error),
# R0301 (critical, treatment-impacting grading), R0370 (mean severity scores),
# R0391 (major threshold defined), R0438 (AHRQ harm levels).
S1_STUDIES = {"R0167", "R0301", "R0370", "R0391", "R0438"}
for base_name, field in [("any_error_supplementary", "n_any_error"), ("omission", "n_omission")]:
    us = [r for r in units(field) if r["study_id"] in S1_STUDIES]
    if len(us) >= 2:
        do_pool(f"{base_name}_S1_severity_graded", field, us)
    else:
        RESULTS[f"{base_name}_S1_severity_graded"] = dict(name=f"{base_name}_S1_severity_graded",
            fittable=False, n_units=len(us), n_studies=len(set(r['study_id'] for r in us)))
    us2 = [r for r in units(field) if not r["preprint"]]
    if len(us2) >= 2:
        do_pool(f"{base_name}_S2_excl_preprints", field, us2)
    else:
        RESULTS[f"{base_name}_S2_excl_preprints"] = dict(name=f"{base_name}_S2_excl_preprints",
            fittable=False, n_units=len(us2), n_studies=len(set(r['study_id'] for r in us2)))
    # S3: overall RoB judgements supplied by coordinator 2026-10-31 (both assessors
    # agreed on all 11 overall judgements; rob-settled.csv pending domain adjudication).
    # Retain only Some concerns studies: R0167, R0370. No Low studies. All others High.
    us3 = [r for r in units(field) if r["study_id"] in {"R0167", "R0370"}]
    if len(us3) >= 2:
        do_pool(f"{base_name}_S3_excl_high_rob", field, us3)
    else:
        RESULTS[f"{base_name}_S3_excl_high_rob"] = dict(name=f"{base_name}_S3_excl_high_rob",
            fittable=False, n_units=len(us3), n_studies=len(set(r['study_id'] for r in us3)))

# Fabrication / inaccuracy sensitivities (pools >=5 units: plan section 6)
for base_name, field in [("fabrication_addition", "n_fabrication"), ("inaccuracy", "n_inaccuracy")]:
    us = [r for r in units(field) if not r["preprint"]]
    if len(us) >= 2: do_pool(f"{base_name}_S2_excl_preprints", field, us)
    us3 = [r for r in units(field) if r["study_id"] in {"R0167", "R0370"}]
    if len(us3) >= 2: do_pool(f"{base_name}_S3_excl_high_rob", field, us3)

# ---------- Subgroups (any-error and omission only) ----------
SUBGROUPS = []
def subgroup(pool_name, field, var_name, keyfun):
    us = units(field) if pool_name not in ("omission_excl_R0354",) else None
    base = RESULTS[pool_name]
    us = base["units"]
    groups = {}
    for r in us: groups.setdefault(keyfun(r), []).append(r)
    entry = dict(pool=pool_name, variable=var_name,
                 levels={k: dict(n_units=len(v), n_studies=len(set(x['study_id'] for x in v)),
                                 total_x=int(sum(x[field] for x in v)),
                                 total_n=int(sum(x['n_assessed'] for x in v)),
                                 crude=float(sum(x[field] for x in v)/sum(x['n_assessed'] for x in v)))
                         for k, v in groups.items()})
    levels_sorted = sorted(groups.keys())
    if len(levels_sorted) >= 2 and all(len(groups[k]) >= 2 for k in levels_sorted) and len(us) >= 5:
        xs = np.array([r[field] for r in us], float); ns = np.array([r["n_assessed"] for r in us], float)
        lev_idx = np.array([levels_sorted.index(keyfun(r)) for r in us])
        mod = fit(xs, ns, levels=lev_idx); null = fit(xs, ns)
        lr = 2*(mod["loglik"] - null["loglik"]); df = len(levels_sorted)-1
        p = float(stats.chi2.sf(lr, df))
        entry.update(interaction_test="GLMM moderator likelihood-ratio test (common tau2)",
                     LR=float(lr), df=df, p_value=p,
                     level_estimates={levels_sorted[i]: dict(pooled=float(expit(mod["mus"][i])),
                        ci_lo=float(expit(mod["mus"][i]-1.96*mod["ses"][i])),
                        ci_hi=float(expit(mod["mus"][i]+1.96*mod["ses"][i]))) for i in range(len(levels_sorted))},
                     tau2_moderator=mod["tau2"])
        # separate per-level fits also reported descriptively
        entry["level_separate_fits"] = {}
        for k in levels_sorted:
            v = groups[k]; fv = fit([x[field] for x in v], [x["n_assessed"] for x in v])
            entry["level_separate_fits"][k] = dict(pooled=fv["pooled"], ci_lo=fv["ci_lo"], ci_hi=fv["ci_hi"], tau2=fv["tau2"])
    else:
        entry.update(interaction_test=None,
                     reason="Not tested: a level has fewer than 2 units and/or the pool has fewer than 5 units (plan section 5). Descriptive only.")
    SUBGROUPS.append(entry)
    return entry

for pname, field in [("any_error_supplementary", "n_any_error"), ("omission", "n_omission")]:
    subgroup(pname, field, "discharge_vs_nondischarge", lambda r: r["subgroup_discharge"])
    subgroup(pname, field, "source_real_vs_synthetic", lambda r: r["source_data"])
    # Blinding, per task wording: blinded vs (unblinded or not reported).
    subgroup(pname, field, "blinding_blinded_vs_unblinded_or_notreported",
             lambda r: "blinded" if r["rater_blinding_settled"].strip() == "blinded" else "unblinded_or_not_reported")
    # Model family: descriptive only (tabulated, no interaction claim unless a level >=3 units
    # and every level >=2; here we tabulate descriptively per the task rule).
    us = RESULTS[pname]["units"]; groups = {}
    for r in us: groups.setdefault(r["model_family"] or "not reported", []).append(r)
    SUBGROUPS.append(dict(pool=pname, variable="model_family_descriptive", interaction_test=None,
        reason="Descriptive tabulation only per task rule (levels too sparse for interaction claims unless a level has at least 3 units and all levels at least 2).",
        levels={k: dict(n_units=len(v), n_studies=len(set(x['study_id'] for x in v)),
                        total_x=int(sum(x[field] for x in v)), total_n=int(sum(x['n_assessed'] for x in v)),
                        crude=float(sum(x[field] for x in v)/sum(x['n_assessed'] for x in v))) for k, v in groups.items()}))

# ---------- Single-unit outcomes ----------
def single(field):
    us = units(field)
    assert len(us) == 1
    r = us[0]; lo, hi = cp_ci(r[field], r["n_assessed"])
    return dict(arm_id=r["arm_id"], label=r["label"], x=r[field], n=r["n_assessed"],
                prop=r[field]/r["n_assessed"], ci_lo=lo, ci_hi=hi)
SINGLE_PRIMARY = single("n_clinically_significant")
SINGLE_HARM = single("n_harm_moderate")

# ---------- Errors per summary (narrative; not pooled) ----------
# R0123: mean 2.84, SD 1.71, n 25 (per-summary). R0391: mean 1.82 (=20/11), no SD.
# R0429: mean 7.11 is per-statement (hallucinated atomic content units), NOT
# comparable with per-summary counts and excluded from any pooling.
EPS = [dict(arm_id="R0123-1", label=SHORT["R0123-1"][0]+", "+SHORT["R0123-1"][1], mean=2.84, sd=1.71, n=25, basis="per summary, printed mean and SD"),
       dict(arm_id="R0391-1", label=SHORT["R0391-1"][0]+", "+SHORT["R0391-1"][1], mean=1.82, sd=None, n=11, basis="per summary, derived mean 20/11, no SD reported"),
       dict(arm_id="R0429-1", label=SHORT["R0429-1"][0]+", "+SHORT["R0429-1"][1], mean=7.11, sd=None, n=671, basis="per STATEMENT (hallucinated atomic content units, 4770/40452 statements); NOT comparable, excluded")]

# ---------- Save machine-readable results ----------
def slim(f):
    if f.get("fittable") is False: return f
    d = {k: f[k] for k in ["name","n_units","n_studies","total_x","total_n","crude","pooled",
                           "ci_lo","ci_hi","tau2","tau","I2","pi_lo","pi_hi","loglik","converged"] if k in f}
    d["studies"] = sorted(set(r["study_id"] for r in f["units"]))
    return d
with open(os.path.join(OUTDIR, "results-internal.json"), "w") as fh:
    json.dump(dict(pools={k: slim(v) for k, v in RESULTS.items()}, subgroups=SUBGROUPS,
                   single_primary=SINGLE_PRIMARY, single_harm=SINGLE_HARM, errors_per_summary=EPS),
              fh, indent=2, default=str)
print("POOLS DONE")
for k, v in RESULTS.items():
    if v.get("fittable") is False:
        print(k, "NOT FITTABLE units=", v["n_units"])
    else:
        print(f"{k}: k={v['n_units']} studies={v['n_studies']} x={v['total_x']} n={v['total_n']} "
              f"pooled={v['pooled']:.4f} CI=({v['ci_lo']:.4f},{v['ci_hi']:.4f}) tau2={v['tau2']:.4f} "
              f"I2={v['I2'] if v['I2'] is None else round(v['I2'],1)} PI=({v['pi_lo']},{v['pi_hi']}) conv={v['converged']}")
for s in SUBGROUPS:
    print("SUBGROUP", s["pool"], s["variable"], "p=", s.get("p_value"), s["levels"].keys() if "levels" in s else "")
print("PRIMARY single:", SINGLE_PRIMARY)
print("HARM single:", SINGLE_HARM)
