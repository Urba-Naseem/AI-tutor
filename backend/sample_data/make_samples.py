"""Render the sample curriculum Markdown as PDF and DOCX (to demonstrate Docling extraction).

    python sample_data/make_samples.py
"""
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "BSCS_curriculum.md"


def to_pdf(lines, out):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    st = getSampleStyleSheet()
    story = []
    for ln in lines:
        if ln.startswith("# "):
            story.append(Paragraph(ln[2:], st["Title"]))
        elif ln.startswith("## "):
            story.append(Paragraph(ln[3:], st["Heading2"]))
        elif ln.startswith("### "):
            story.append(Paragraph(ln[4:], st["Heading3"]))
        elif ln.strip():
            story.append(Paragraph(ln.lstrip("- ").replace("->", "maps to").replace("—", "-"), st["BodyText"]))
        else:
            story.append(Spacer(1, 4))
    SimpleDocTemplate(str(out), pagesize=A4).build(story)


def to_docx(lines, out):
    import docx

    d = docx.Document()
    for ln in lines:
        if ln.startswith("# "):
            d.add_heading(ln[2:], 0)
        elif ln.startswith("## "):
            d.add_heading(ln[3:], 1)
        elif ln.startswith("### "):
            d.add_heading(ln[4:], 2)
        elif ln.startswith("- "):
            d.add_paragraph(ln[2:], style="List Bullet")
        elif ln.strip():
            d.add_paragraph(ln)
    d.save(out)


if __name__ == "__main__":
    lines = SRC.read_text(encoding="utf-8").splitlines()
    to_pdf(lines, HERE / "BSCS_curriculum.pdf")
    to_docx(lines, HERE / "BSCS_curriculum.docx")
    print("Wrote BSCS_curriculum.pdf and BSCS_curriculum.docx")
