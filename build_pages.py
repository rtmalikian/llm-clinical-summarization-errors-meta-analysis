#!/usr/bin/env python3
"""Generic journal-style GitHub Pages builder, adapted from the viral
taste-loss review's build_pages.py (PLOS/BMJ style). Config is injected
at the top by make.py; this file is copied into each repo as build_pages.py
with CONFIG filled in.
Run: ~/workspace/venvs/pubtools/bin/python build_pages.py
"""
import html
import re

import markdown

CONFIG = {'repo': 'llm-clinical-summarization-errors-meta-analysis', 'title': 'Clinically Significant Errors in Large Language Model-Generated Clinical Summaries: A Systematic Review and Meta-analysis of Omissions, Inaccuracies and Fabrications per Summary', 'subtitle': 'A Cochrane-level systematic review and meta-analysis', 'doi': '10.5281/zenodo.23847500', 'published': '31 October 2026', 'published_iso': '2026/10/31', 'dc_date': '2026-10-31', 'version': 'Version 1.0', 'topic': 'Clinical AI Safety', 'bibkey': 'llmsummarization', 'has_docx': False, 'licence': 'Creative Commons Attribution 4.0 International (CC BY 4.0)', 'licence_sentence': 'This is an open access article distributed under the terms of the Creative Commons Attribution 4.0 International Licence (CC BY 4.0), which permits use, distribution, and reproduction in any medium, provided the original author and source are credited. This review makes no clinical or medication recommendation.', 'keywords': ['large language models', 'clinical summarization', 'discharge summaries', 'medical errors', 'omissions', 'fabrications', 'hallucination', 'patient safety', 'clinical documentation', 'systematic review', 'meta-analysis', 'GRADE', 'PRISMA'], 'registration': 'No PROSPERO registration number was issued for this review; a PROSPERO-ready form was prepared on 31 October 2026, before screening closed, and none is claimed.', 'key_findings': ['11 studies (22 arms: 21 LLM, 1 human) included, from 991 records found.', 'The primary outcome could not be pooled: only 1 of the 11 studies reported the proportion of summaries with at least one clinically significant error (13 of 62 summaries, 21.0%).', 'By error type: omissions pooled at 20.7% of summaries, fabrication or addition at 17.6%, inaccuracy at 27.9%.', 'Of 48 reports assessed in full, 31 (65%) reported no extractable per-summary error count at all.', 'Certainty was rated very low for every rateable outcome (GRADE).']}

TITLE = CONFIG["title"]
SUBTITLE = CONFIG["subtitle"]
ARTICLE_TYPE = "Systematic Review &amp; Meta-analysis"
AUTHOR = "Raphael Malikian"
AFFIL = "Independent Researcher, Palmdale, CA, USA"
EMAIL = "rtmalikian@gmail.com"
ORCID = "0009-0008-4326-4205"
REPO_SLUG = CONFIG["repo"]
REPO = f"https://github.com/rtmalikian/{REPO_SLUG}"
PAGES = f"https://rtmalikian.github.io/{REPO_SLUG}/"
HUB = "https://rtmalikian.github.io/systematic-reviews/"
DOI = CONFIG["doi"]
DOI_URL = f"https://doi.org/{DOI}"
ZENODO_RECORD = f"https://zenodo.org/records/{DOI.split('.')[-1]}"
PUBLISHED = CONFIG["published"]
PUBLISHED_ISO = CONFIG["published_iso"]
DC_DATE = CONFIG["dc_date"]
VERSION = CONFIG["version"]
KEYWORDS = CONFIG["keywords"]
LICENCE = CONFIG["licence"]
LICENCE_SENTENCE = CONFIG["licence_sentence"]
SERIES = "Systematic Reviews"
TOPIC = CONFIG["topic"]
HAS_DOCX = CONFIG["has_docx"]
REGISTRATION = CONFIG["registration"]
ARTICLE_INFO_EXTRA = CONFIG.get("article_info_extra", "")
KEY_FINDINGS = CONFIG.get("key_findings", [])

CITATION = f"Malikian R. {TITLE}. {VERSION}; 2026. DOI: {DOI}"
BIBTEX = f"""@misc{{malikian2026{CONFIG['bibkey']},
  author       = {{Malikian, Raphael}},
  title        = {{{TITLE}}},
  year         = {{2026}},
  publisher    = {{Zenodo}},
  doi          = {{{DOI}}},
  url          = {{{DOI_URL}}},
  note         = {{Cochrane-level systematic review and meta-analysis}}
}}"""
RIS = f"""TY  - GEN
AU  - Malikian, Raphael
TI  - {TITLE}
PY  - 2026
DO  - {DOI}
UR  - {DOI_URL}
ER  -"""

EXTS = ["tables", "sane_lists", "toc"]
MAIN_SECTIONS = ["background", "objectives", "methods", "results",
                 "discussion", "authors-conclusions", "conclusions"]


def render(md_text):
    return markdown.markdown(md_text, extensions=EXTS)


def wrap_figures(html_text):
    pat = re.compile(r'<p><img alt="([^"]*)" src="([^"]*)"(?:\s*/)?></p>')

    def repl(m):
        cap, src = m.group(1), m.group(2)
        return (f'<figure><img alt="{cap}" src="{src}">'
                f'<figcaption>{cap}</figcaption></figure>')

    return pat.sub(repl, html_text)


def slug_base(hid):
    return re.sub(r"^\d+-", "", hid)


def number_sections(html_text):
    n = 0
    for base in MAIN_SECTIONS:
        def try_num(m):
            nonlocal n
            n += 1
            return f'{m.group(1)}<span class="secno">{n}</span> '
        html_text, cnt = re.subn(
            rf'(<h2 id="(?:\d+-)?{base}">)', lambda m: try_num(m),
            html_text, count=1)
    return html_text


def number_references(html_text):
    ref_i = html_text.find('<h2 id="references">')
    if ref_i < 0:
        ref_i = html_text.find('<h2 id="')
        return html_text
    nxt = html_text.find('<h2 id="', ref_i + 10)
    end = nxt if nxt > 0 else len(html_text)
    chunk = html_text[ref_i:end]
    chunk = chunk.replace("<ul>", '<ol class="refs">', 1)
    chunk = chunk.replace("</ul>", "</ol>", 1)
    return html_text[:ref_i] + chunk + html_text[end:]


def h2_sections(html_text):
    out = []
    for hid, title in re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', html_text):
        clean = re.sub(r"<[^>]+>", "", title).strip()
        out.append((hid, clean))
    return out


def main():
    md_text = open("manuscript.md").read()
    abs_i = md_text.index("## Abstract")
    pls_i = md_text.index("## Plain language summary")
    sof_i = md_text.index("## Summary of findings")
    abstract_html = wrap_figures(render(md_text[abs_i:pls_i]))
    pls_html = wrap_figures(render(md_text[pls_i:sof_i]))
    body_html = number_references(
        number_sections(wrap_figures(render(md_text[sof_i:]))))

    contents = []
    for chunk in (abstract_html, pls_html, body_html):
        contents.extend(h2_sections(chunk))
    contents_html = "".join(
        f'<li><a href="#{hid}">{html.escape(title)}</a></li>'
        for hid, title in contents)

    kw_meta = "\n".join(
        f'<meta name="citation_keyword" content="{html.escape(k)}">'
        for k in KEYWORDS)
    kw_list = "".join(f"<li>{html.escape(k)}</li>" for k in KEYWORDS)
    findings_html = ""
    if KEY_FINDINGS:
        fl = "".join(f"<li>{f}</li>" for f in KEY_FINDINGS)
        findings_html = (f'<section class="keyfindings"><h2>Key findings</h2>'
                         f"<ul>{fl}</ul></section>")
    share_url = ("https://twitter.com/intent/tweet?text="
                 + html.escape(TITLE.replace(" ", "%20"))
                 + "&url=" + PAGES)
    docx_action = (f'<a href="{REPO}/raw/main/manuscript.docx">Download DOCX</a>'
                   if HAS_DOCX else "")
    docx_dl = (f'<a class="btn alt" href="{REPO}/raw/main/manuscript.docx">Download DOCX</a>'
               if HAS_DOCX else "")

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(TITLE)} | {SERIES}</title>
<link rel="canonical" href="{PAGES}">
<meta name="description" content="{html.escape(TITLE)}. {SUBTITLE}. By Raphael Malikian. Zenodo DOI {DOI}.">
<meta name="citation_title" content="{html.escape(TITLE)}">
<meta name="citation_author" content="Malikian, Raphael">
<meta name="citation_publication_date" content="{PUBLISHED_ISO}">
<meta name="citation_doi" content="{DOI}">
<meta name="citation_pdf_url" content="{REPO}/raw/main/manuscript.pdf">
<meta name="citation_publisher" content="Zenodo">
<meta name="citation_language" content="en">
{kw_meta}
<meta name="DC.title" content="{html.escape(TITLE)}">
<meta name="DC.creator" content="Raphael Malikian">
<meta name="DC.date" content="{DC_DATE}">
<meta name="DC.identifier" content="{DOI_URL}">
<meta name="DC.type" content="Text">
<meta name="DC.rights" content="{LICENCE}">
<meta property="og:title" content="{html.escape(TITLE)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{PAGES}">
<meta name="twitter:card" content="summary">
<style>
:root{{--navy:#14406e;--navy2:#1d5aa8;--ink:#1a1a1a;--mut:#5c6670;--line:#d9dee4;
--rule:#9aa7b4;--panel:#f7f9fb;--boxbg:#fbfbf8}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:Georgia,'Times New Roman',serif;color:var(--ink);background:#fff;line-height:1.6}}
.wrap{{max-width:1200px;margin:0 auto;padding:0 22px}}
a{{color:var(--navy2)}}
.masthead{{border-top:5px solid var(--navy);border-bottom:1px solid var(--ink);padding:20px 0 14px}}
.wordmark{{font-size:37px;font-weight:bold;letter-spacing:.01em;color:#0e2a47;line-height:1.05}}
.mast-sub{{font-family:Helvetica,Arial,sans-serif;font-size:12.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--mut);margin-top:5px}}
.journalnav{{border-bottom:1px solid var(--line)}}
.journalnav .wrap{{display:flex;gap:26px;padding-top:8px;padding-bottom:8px}}
.journalnav a{{font-family:Helvetica,Arial,sans-serif;font-size:13px;font-weight:bold;letter-spacing:.06em;text-transform:uppercase;color:#24313d;text-decoration:none}}
.journalnav a:hover{{color:var(--navy2);text-decoration:underline}}
.crumb{{font-family:Helvetica,Arial,sans-serif;font-size:12.5px;color:var(--mut);margin:18px 0 0}}
.crumb a{{color:var(--mut);text-decoration:none}} .crumb a:hover{{text-decoration:underline}}
.typerow{{display:flex;align-items:center;gap:12px;margin:10px 0 0;flex-wrap:wrap}}
.arttype{{font-family:Helvetica,Arial,sans-serif;font-size:13px;font-weight:bold;letter-spacing:.13em;text-transform:uppercase;color:var(--navy)}}
.oa{{font-family:Helvetica,Arial,sans-serif;font-size:11.5px;font-weight:bold;letter-spacing:.08em;text-transform:uppercase;color:#14632d;border:1px solid #14632d;border-radius:3px;padding:2px 8px}}
.article-head{{border-bottom:2px solid var(--ink);padding-bottom:16px}}
h1{{font-size:33px;line-height:1.22;margin:14px 0 8px;color:#101c28;font-weight:bold}}
.standfirst{{font-size:17.5px;color:#3c4753;margin:0 0 18px}}
.authors{{font-size:17px;margin:0 0 3px}}
.authors sup{{font-size:11px}}
.affil{{font-size:14px;color:#3c4753;margin:0 0 3px}}
.corr{{font-size:14px;color:#3c4753;margin:0 0 12px}}
.publine{{font-family:Helvetica,Arial,sans-serif;font-size:13.5px;color:#24313d;margin:0 0 5px}}
.citeline{{font-size:14.5px;color:#24313d;margin:0}}
.actions{{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0 4px}}
.actions a,.actions button{{font-family:Helvetica,Arial,sans-serif;font-size:13.5px;font-weight:bold;text-decoration:none;border:1px solid var(--navy);border-radius:3px;padding:8px 16px;color:var(--navy);background:#fff;cursor:pointer}}
.actions a.primary{{background:var(--navy);color:#fff}}
.actions a:hover,.actions button:hover{{background:#e8eef5}}
.actions a.primary:hover{{background:var(--navy2)}}
.grid{{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:40px;margin-top:22px}}
@media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
article h2{{font-size:21px;color:#101c28;border-bottom:1px solid var(--rule);padding-bottom:5px;margin:36px 0 12px}}
article h2 .secno{{color:var(--navy)}}
article h3{{font-size:17px;color:#101c28;margin:26px 0 8px}}
article h4{{font-size:15px;color:#101c28;margin:20px 0 6px}}
article p{{margin:0 0 11px}}
article table{{border-collapse:collapse;width:100%;font-size:13px;margin:16px 0;line-height:1.45}}
article th{{background:none;color:var(--ink);text-align:left;font-weight:bold;padding:6px 8px;border-top:2.5px solid #101c28;border-bottom:1px solid #101c28}}
article td{{border:none;padding:5px 8px;vertical-align:top}}
article tbody tr:last-child td{{border-bottom:2.5px solid #101c28}}
article figure{{margin:22px 0}}
article figure img{{max-width:100%;border:1px solid var(--line)}}
article figcaption{{font-size:13.5px;color:#24313d;margin-top:7px;font-family:Helvetica,Arial,sans-serif;line-height:1.5}}
.abstract-panel{{background:var(--panel);border:1px solid var(--line);padding:16px 22px 8px;margin:4px 0 10px}}
.abstract-panel h2{{border:none;font-size:14px;letter-spacing:.13em;text-transform:uppercase;color:var(--navy);margin:0 0 10px;padding:0;font-family:Helvetica,Arial,sans-serif}}
.keyfindings{{background:var(--boxbg);border:1px solid var(--line);border-top:3px solid var(--navy);padding:13px 20px 5px;margin:20px 0}}
.keyfindings h2{{border:none;font-size:13.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--navy);margin:0 0 8px;padding:0;font-family:Helvetica,Arial,sans-serif}}
.keyfindings ul{{margin:4px 0 10px;padding-left:20px}} .keyfindings li{{margin-bottom:6px}}
ol.refs{{padding-left:0;list-style-position:outside;margin-left:2.1em}}
ol.refs li{{margin-bottom:7px;padding-left:.4em}}
aside .box{{border:1px solid var(--line);background:#fff;padding:14px 16px;margin-bottom:18px}}
aside h3{{margin:0 0 9px;font-size:13px;font-family:Helvetica,Arial,sans-serif;text-transform:uppercase;letter-spacing:.07em;color:var(--navy);border-bottom:1px solid var(--line);padding-bottom:6px}}
aside p,aside li{{font-size:13.5px}}
aside ul{{margin:6px 0;padding-left:18px}}
aside ul.contents{{list-style:none;padding-left:0}} aside ul.contents li{{margin-bottom:5px}}
aside ul.contents a{{color:#24313d;text-decoration:none}} aside ul.contents a:hover{{text-decoration:underline;color:var(--navy2)}}
.dl a.btn{{display:block;background:var(--navy);color:#fff;text-align:center;padding:10px;border-radius:3px;text-decoration:none;font-family:Helvetica,Arial,sans-serif;font-weight:bold;margin-bottom:8px}}
.dl a.btn:hover{{background:var(--navy2)}}
.dl a.alt{{background:#fff;color:var(--navy);border:1px solid var(--navy);font-weight:normal}}
.dl p{{color:var(--mut);margin:6px 0 0}}
pre{{white-space:pre-wrap;font-size:11px;background:#f6f4ef;padding:8px;line-height:1.4}}
button.copy{{font-size:12px;cursor:pointer}}
footer{{border-top:2px solid var(--ink);margin-top:44px;padding:16px 0 36px;font-size:13.5px;color:#3c4753}}
footer .seriesline{{font-family:Helvetica,Arial,sans-serif;font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:var(--mut);margin-top:10px}}
@media print{{
 .masthead .journalnav,.crumb,.actions,aside,button.copy{{display:none}}
 .grid{{grid-template-columns:1fr}}
 body{{font-size:11pt;line-height:1.5}} a{{color:#000;text-decoration:none}}
 article h2{{break-after:avoid}} article table,article figure{{break-inside:avoid}}
}}
</style>
</head>
<body>
<div class="masthead"><div class="wrap">
<div class="wordmark">{SERIES}</div>
<div class="mast-sub">Raphael Malikian · Cochrane-Level Evidence Syntheses</div>
</div></div>
<nav class="journalnav"><div class="wrap">
<a href="{HUB}#reviews">Browse</a>
<a href="{HUB}#method">About</a>
<a href="{HUB}">Systematic Reviews Hub</a>
<a href="{REPO}">GitHub</a>
</div></nav>
<div class="wrap">
<p class="crumb"><a href="{HUB}">Systematic Reviews Hub</a> &rsaquo; {TOPIC} &rsaquo; Systematic Review</p>
<div class="typerow"><span class="arttype">{ARTICLE_TYPE}</span><span class="oa">Open Access</span></div>
<header class="article-head">
<h1>{html.escape(TITLE)}</h1>
<p class="standfirst">{SUBTITLE}</p>
<p class="authors"><strong>{AUTHOR}</strong><sup>1</sup></p>
<p class="affil"><sup>1</sup> {AFFIL}</p>
<p class="corr">Corresponding author: {AUTHOR}, <a href="mailto:{EMAIL}">{EMAIL}</a> · ORCID <a href="https://orcid.org/{ORCID}">{ORCID}</a></p>
<p class="publine">Published: {PUBLISHED} &middot; {VERSION}</p>
<p class="citeline">Malikian R. {TITLE}. {VERSION}; 2026. DOI: <a href="{DOI_URL}">{DOI_URL}</a></p>
</header>
<div class="actions">
<a class="primary" href="{REPO}/raw/main/manuscript.pdf">Download PDF</a>
{docx_action}
<button type="button" onclick="window.print()">Print</button>
<a href="#cite">Cite</a>
<a href="{share_url}" target="_blank" rel="noopener">Share</a>
</div>
<div class="grid">
<article>
<section class="abstract-panel">
{abstract_html}
</section>
{pls_html}
{findings_html}
{body_html}
</article>
<aside>
<div class="box dl">
<h3>Download</h3>
<a class="btn" href="{REPO}/raw/main/manuscript.pdf">Download PDF (full article)</a>
{docx_dl}
<a class="btn alt" href="{REPO}/raw/main/manuscript.md">Markdown source</a>
<p>One click — no sign-up, no paywall.</p>
</div>
<div class="box" id="cite">
<h3>Cite this article</h3>
<p>{html.escape(CITATION)}</p>
<p><strong>BibTeX</strong> <button class="copy" onclick="navigator.clipboard.writeText(document.getElementById('bib').innerText)">Copy</button></p>
<pre id="bib">{html.escape(BIBTEX)}</pre>
<p><strong>RIS</strong> <button class="copy" onclick="navigator.clipboard.writeText(document.getElementById('ris').innerText)">Copy</button></p>
<pre id="ris">{html.escape(RIS)}</pre>
</div>
<div class="box">
<h3>Article information</h3>
<p>Published: {PUBLISHED} ({VERSION}).</p>
<p>Funding: none. Conflicts of interest: none.</p>
<p>Correspondence: {AUTHOR}, <a href="mailto:{EMAIL}">{EMAIL}</a>, Palmdale, CA, USA. ORCID <a href="https://orcid.org/{ORCID}">{ORCID}</a>.</p>
<p>Registration: {REGISTRATION}</p>
<p>Peer review: multi-agent pre-submission peer review (Gates 0–6 plus a feedback loop) under the author's accountability; the full record, including every reviewer item and its closure, is in the repository's peer-review materials where present. This was internal pre-submission review, not journal peer review.</p>
<p>Methods: Cochrane Handbook v6.5; PRISMA 2020 and PRISMA-S; GRADE. Carried out by a multi-agent LLM team with the author accountable for every number (see the team log in the repository).</p>
{ARTICLE_INFO_EXTRA}
</div>
<div class="box">
<h3>Contents</h3>
<ul class="contents">{contents_html}</ul>
</div>
<div class="box">
<h3>Keywords</h3>
<ul>{kw_list}</ul>
</div>
<div class="box">
<h3>Links</h3>
<ul>
<li><a href="{REPO}">GitHub repository</a></li>
<li><a href="{ZENODO_RECORD}">Zenodo record</a> (DOI: <a href="{DOI_URL}">{DOI}</a>)</li>
<li><a href="{HUB}">Systematic reviews hub</a></li>
<li><a href="https://orcid.org/{ORCID}">ORCID</a></li>
</ul>
</div>
</aside>
</div>
<footer>
<p>{LICENCE_SENTENCE}</p>
<p>© 2026 {AUTHOR}. DOI: <a href="{DOI_URL}">{DOI_URL}</a></p>
<p class="seriesline">{SERIES} — Raphael Malikian · Cochrane-Level Evidence Syntheses</p>
</footer>
</div>
</body>
</html>"""
    open("index.html", "w").write(page)
    print("wrote index.html", len(page), "bytes;",
          len(contents), "contents entries")


if __name__ == "__main__":
    main()
