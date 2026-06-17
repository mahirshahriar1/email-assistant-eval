"""Render report/REPORT.md -> report/REPORT.pdf (and REPORT.html).

Pure-Python, no system dependencies (markdown + xhtml2pdf). The HTML is always written;
the PDF is written if xhtml2pdf is available.

    python -m scripts.render_report
"""
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "report" / "REPORT.md"
HTML = ROOT / "report" / "REPORT.html"
PDF = ROOT / "report" / "REPORT.pdf"

CSS = """
@page { size: A4; margin: 1.6cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10.5pt; color: #1a1a1a; line-height: 1.45; }
h1 { font-size: 19pt; border-bottom: 2px solid #333; padding-bottom: 4px; }
h2 { font-size: 14pt; margin-top: 18px; color: #222; border-bottom: 1px solid #ccc; padding-bottom: 2px; }
h3 { font-size: 11.5pt; margin-top: 12px; color: #333; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 8.8pt; }
th, td { border: 1px solid #bbb; padding: 4px 6px; text-align: left; }
th { background: #f0f0f0; }
code { background: #f4f4f4; padding: 1px 3px; font-size: 9pt; }
blockquote { border-left: 3px solid #ccc; margin: 6px 0; padding: 2px 10px; color: #444; font-style: italic; }
strong { color: #000; }
"""


def main():
    md_text = MD.read_text(encoding="utf-8")
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    html = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {HTML}")

    try:
        from xhtml2pdf import pisa
        with open(PDF, "wb") as f:
            result = pisa.CreatePDF(html, dest=f)
        if result.err:
            print("PDF generation reported errors; HTML is available as a fallback.")
        else:
            print(f"Wrote {PDF}")
    except ImportError:
        print("xhtml2pdf not installed -> skipped PDF. Open REPORT.html and 'Save as PDF', "
              "or `pip install xhtml2pdf` and re-run.")


if __name__ == "__main__":
    main()
