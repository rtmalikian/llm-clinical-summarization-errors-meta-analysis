#!/usr/bin/env python3
"""
Forest plots for Review 3 fitted pools.
Page-fit rules (shipping gate): A4 portrait printable width, each figure
max 170 mm wide and max 200 mm tall; pools with more than 12 rows are
split into panels of at most 12 rows (panel-a, panel-b). Every plot
draws the pooled estimate as a DIAMOND (centre = pooled proportion,
tips = 95% CI) and the prediction interval as a bar under the diamond.
Axis label: 'Proportion of summaries'. Study labels are short
(first author, year, arm). All fonts at least 8 pt at final size.
Unit intervals are Clopper-Pearson exact intervals.
Software: Python matplotlib (see analysis fallback disclosure).
"""
import csv, json, math, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from scipy import stats

BASE = os.path.expanduser("~/workspace/publications/weekly-series/meta-analysis-clinical-summarization-errors/review3")
FIGDIR = os.path.join(BASE, "stage4-analysis/figures"); os.makedirs(FIGDIR, exist_ok=True)
with open(os.path.join(BASE, "stage4-analysis/results-internal.json")) as f: RES = json.load(f)
with open(os.path.join(BASE, "stage3-extraction/extraction-settled.csv"), newline='', encoding='utf-8') as f:
    ROWS = {r["arm_id"]: r for r in csv.DictReader(f)}
SHORT = {
 "CC2-03-1": "Song 2025, Ko-Llama3", "R0047-1": "Tung 2024, GPT-4",
 "R0144-1": "Watcharasarn 2025, GPT-4o", "R0167-1": "Williams 2025, GPT-4",
 "R0167-2": "Williams 2025, GPT-3.5", "R0301-2": "Park 2026, GPT-4o pilot",
 "R0354-1": "Dhanda 2026, llama3.2 A", "R0354-2": "Dhanda 2026, llama3.2 B",
 "R0354-3": "Dhanda 2026, gemma3 A", "R0354-4": "Dhanda 2026, gemma3 B",
 "R0354-5": "Dhanda 2026, qwen2.5 A", "R0354-6": "Dhanda 2026, qwen2.5 B",
 "R0354-7": "Dhanda 2026, gemma2 A", "R0354-8": "Dhanda 2026, gemma2 B",
 "R0370-1": "Jolin-Rodrigo 2026, gemini-2.5-flash", "R0370-2": "Jolin-Rodrigo 2026, gpt-oss-20b",
 "R0391-1": "Nakano 2026, Ubie AI", "R0429-1": "Bodanki 2026, Epic GPT-4",
 "R0438-1": "Grolleau 2026, Gemini 2.5 Pro",
}
POOLS = [("any_error_supplementary", "n_any_error", "Any error (supplementary pool)"),
         ("omission", "n_omission", "Omission"),
         ("fabrication_addition", "n_fabrication", "Fabrication / addition"),
         ("inaccuracy", "n_inaccuracy", "Inaccuracy")]

def cp(x, n):
    lo = 0.0 if x == 0 else float(stats.beta.ppf(0.025, x, n-x+1))
    hi = 1.0 if x == n else float(stats.beta.ppf(0.975, x+1, n-x))
    return lo, hi

MM = 1/25.4
for name, field, title in POOLS:
    pool = RES["pools"][name]
    # rebuild unit list in settled-sheet order from the pool's studies is ambiguous;
    # unit arm ids are recovered from analysis order: use settled rows with the field set,
    # restricted for the main pools (no filters apply to main pools).
    arms = [r for r in ROWS.values() if r["arm_type"] == "llm" and r[field].strip() != ""]
    assert len(arms) == pool["n_units"], (name, len(arms), pool["n_units"])
    panels = [arms[i:i+12] for i in range(0, len(arms), 12)]
    for pi, panel in enumerate(panels):
        suffix = "" if len(panels) == 1 else f"-panel-{'ab'[pi]}"
        nrows = len(panel)
        height_mm = min(200, 42 + nrows*11 + 22)  # title/header + rows + diamond/PI rows
        fig, ax = plt.subplots(figsize=(170*MM, height_mm*MM))
        ys = list(range(nrows+2, 1, -1))  # data rows top to bottom; rows 1 and 0 for diamond/PI
        for y, r in zip(ys, panel):
            x, n = int(r[field]), int(r["n_assessed"]); p = x/n; lo, hi = cp(x, n)
            ax.plot([lo, hi], [y, y], color="#444444", lw=1.2, solid_capstyle="round")
            ax.plot([p], [y], marker="s", ms=max(4, min(9, n**0.5/1.6)), color="#1a5276")
            ax.text(-0.03, y, SHORT[r["arm_id"]], ha="right", va="center", fontsize=8, transform=ax.get_yaxis_transform())
            ax.text(1.02, y, f"{x}/{n}  {p:.2f} [{lo:.2f}, {hi:.2f}]", ha="left", va="center", fontsize=8, transform=ax.get_yaxis_transform())
        # Diamond on pooled row (only drawn in full on panel-a when split; repeated on each panel for readability, labelled)
        yD = 1
        pooled, clo, chi = pool["pooled"], pool["ci_lo"], pool["ci_hi"]
        diamond = Polygon([(clo, yD), (pooled, yD+0.38), (chi, yD), (pooled, yD-0.38)], closed=True, color="#922b21")
        ax.add_patch(diamond)
        ax.text(-0.03, yD, "Pooled (GLMM)", ha="right", va="center", fontsize=8, fontweight="bold", transform=ax.get_yaxis_transform())
        ax.text(1.02, yD, f"{pooled:.2f} [{clo:.2f}, {chi:.2f}]", ha="left", va="center", fontsize=8, fontweight="bold", transform=ax.get_yaxis_transform())
        if pool["pi_lo"] is not None:
            yP = 0
            ax.plot([pool["pi_lo"], pool["pi_hi"]], [yP, yP], color="#922b21", lw=3, solid_capstyle="butt")
            ax.plot([pool["pi_lo"], pool["pi_hi"]], [yP, yP], marker="|", ms=10, color="#922b21")
            ax.text(-0.03, yP, "Prediction interval", ha="right", va="center", fontsize=8, transform=ax.get_yaxis_transform())
            ax.text(1.02, yP, f"[{pool['pi_lo']:.2f}, {pool['pi_hi']:.2f}]", ha="left", va="center", fontsize=8, transform=ax.get_yaxis_transform())
        ax.set_xlim(0, 1); ax.set_ylim(-0.7, nrows+2.7)
        ax.set_yticks([])
        for s in ["left", "right", "top"]: ax.spines[s].set_visible(False)
        ax.tick_params(axis="x", labelsize=8)
        ax.set_xlabel("Proportion of summaries", fontsize=9)
        ax.axvline(pooled, color="#922b21", lw=0.7, ls="--", alpha=0.6)
        ax.grid(axis="x", color="#dddddd", lw=0.5)
        ttl = f"{title}: forest plot" + (f" (panel {'AB'[pi]} of {len(panels)})" if len(panels) > 1 else "")
        ax.set_title(f"{ttl}\nx/n, Clopper-Pearson 95% CI; diamond = pooled GLMM (95% CI)", fontsize=9, loc="left")
        fig.tight_layout()
        for ext in ["png", "pdf"]:
            fig.savefig(os.path.join(FIGDIR, f"forest-{name.replace('_supplementary','')}{suffix}.{ext}"), dpi=300)
        plt.close(fig)
        print("wrote", name, suffix, f"{170}x{height_mm}mm rows={nrows}")
print("FIGURES DONE")
