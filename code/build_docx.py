import re
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from PIL import Image as PILImage

BASE = "/home/hatch/workspace/publications/weekly-series/meta-analysis-clinical-summarization-errors/review3/stage5-manuscript/"
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
for s in doc.sections:
    s.left_margin = s.right_margin = Inches(0.8)
    s.top_margin = Inches(0.85); s.bottom_margin = Inches(0.85)
USABLE = 6.67
styles = doc.styles['Normal']; styles.font.name = 'Calibri'; styles.font.size = Pt(11)
styles.paragraph_format.space_after = Pt(6); styles.paragraph_format.line_spacing = 1.07

WIDTHS = {5:[1.55,1.02,1.78,0.72,1.60], 8:[0.72,0.40,0.70,0.70,0.60,1.62,0.70,1.23],
          6:[0.92,1.02,1.02,1.90,0.92,0.89], 9:[1.42,0.48,0.52,0.60,0.60,1.30,0.55,0.55,0.65],
          3:[1.52,1.22,3.93], 4:[1.7,1.2,1.9,1.87]}
def set_cell(cell, text, size, bold=False):
    cell.text = ""
    p = cell.paragraphs[0]; p.paragraph_format.space_after = Pt(2)
    for part in re.split(r'(\*\*.*?\*\*)', text):
        r = p.add_run(part[2:-2] if part.startswith('**') else part)
        r.bold = bold or part.startswith('**'); r.font.size = Pt(size)

def add_table(rows):
    ncol = len(rows[0])
    t = doc.add_table(rows=len(rows), cols=ncol); t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    widths = WIDTHS.get(ncol) or [USABLE/ncol]*ncol
    size = 8 if ncol >= 8 else (8.5 if ncol >= 6 else 9.5)
    if ncol == 5: size = 9
    if ncol == 3: size = 8.5
    for ri, r in enumerate(rows):
        tr = t.rows[ri]._tr
        trPr0 = tr.get_or_add_trPr(); cs = OxmlElement('w:cantSplit'); trPr0.append(cs)
        if ri == 0:
            trPr = tr.get_or_add_trPr(); shd = OxmlElement('w:tblHeader'); trPr.append(shd)
        for ci, c in enumerate(r):
            cell = t.cell(ri, ci); cell.width = Inches(widths[ci])
            set_cell(cell, c, size, bold=(ri == 0))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t

def clean(t): return re.sub(r'\*\*(.*?)\*\*', r'\1', t).strip()
def add_para(line, size=11, bold_all=False, italic=False, align=None):
    p = doc.add_paragraph()
    if align: p.alignment = align
    for part in re.split(r'(\*\*.*?\*\*)', line):
        if not part: continue
        r = p.add_run(part[2:-2] if part.startswith('**') else part)
        r.bold = bold_all or part.startswith('**'); r.italic = italic; r.font.size = Pt(size)
    return p

lines = open(BASE + "manuscript.md", encoding="utf-8").read().splitlines()
i = 0; first_title = True
while i < len(lines):
    line = lines[i]
    if line.startswith("|") and i + 1 < len(lines) and lines[i+1].startswith("|---"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')]); i += 1
        rows = [r for r in rows if not all(set(c) <= set('-: ') for c in r)]
        add_table(rows); continue
    m = re.match(r'!\[(.*?)\]\((.*?)\)', line.strip())
    if m:
        caption, fname = m.group(1), m.group(2)
        iw, ih = PILImage.open(BASE + fname).size
        hcap = 6.2 if "omission" in fname else 8.4
        scale = min(USABLE / (iw / 300), hcap / (ih / 300))
        pic_p = doc.add_paragraph(); pic_p.alignment = WD_ALIGN_PARAGRAPH.CENTER; pic_p.paragraph_format.keep_with_next = True; pic_p.paragraph_format.space_after = Pt(2)
        pic_p.add_run().add_picture(BASE + fname, width=Inches(iw / 300 * scale))
        cp = add_para(caption, size=8.5); cp.paragraph_format.keep_with_previous = True
        i += 1; continue
    if line.startswith("# "):
        h = doc.add_heading(clean(line[2:]), level=0)
        for r in h.runs: r.font.size = Pt(19); r.font.color.rgb = RGBColor(0,0,0)
    elif line.startswith("## "):
        doc.add_heading(clean(line[3:]), level=1)
    elif line.startswith("### "):
        h = doc.add_heading(clean(line[4:]), level=2); h.paragraph_format.keep_with_next = True
    elif line.startswith("**Table ") or line.startswith("**Figure "):
        p = add_para(clean(line), size=10, bold_all=True); p.paragraph_format.keep_with_next = True
    elif line.strip().startswith("- "):
        add_para(line.strip()[2:], size=11)
    elif line.strip():
        add_para(line, size=11)
    i += 1

doc.save(BASE + "manuscript.docx")
print("docx built")
