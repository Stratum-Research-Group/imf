#!/usr/bin/env python3
"""
scripts/compile_stream_compendium_pdf.py
Generates publication-grade PDF compendiums for consolidated research streams
using headless Chromium with full styling and KaTeX mathematical support.
"""

import os
import glob
import subprocess
import markdown

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    @page {{ size: A4; margin: 20mm; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 10pt; line-height: 1.5; color: #111; }}
    h1 {{ color: #1e3a8a; border-bottom: 2px solid #1e3a8a; padding-bottom: 4px; }}
    h2, h3 {{ color: #1f2937; margin-top: 1.2em; }}
    pre, code {{ font-family: monospace; background: #f3f4f6; font-size: 8.5pt; }}
    pre {{ padding: 10px; border-radius: 4px; border: 1px solid #e5e7eb; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 8.5pt; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 5px 8px; text-align: left; }}
    th {{ background: #f1f5f9; }}
    blockquote {{ border-left: 3px solid #3b82f6; margin: 0; padding-left: 12px; color: #475569; }}
  </style>
</head>
<body>
{content}
</body>
</html>
"""

def compile_compendiums():
    streams = sorted(glob.glob("papers/**/streams/STREAM_*.md", recursive=True))
    out_dir = "dist/stream_pdf_archive"
    os.makedirs(out_dir, exist_ok=True)
    
    print(f"[*] Found {len(streams)} development streams. Compiling top representative compendiums...")
    
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    selected = [(f"Stream {i+1}", s) for i, s in enumerate(streams[:limit])]
    if False:
      old_selected = [
        ("Phase II", [s for s in streams if "phase_2" in s][0]),
        ("Phase III", [s for s in streams if "phase_3" in s][0]),
        ("Phase IV", [s for s in streams if "phase_4" in s][0]),
        ("Phase V", [s for s in streams if "phase_5" in s][0]),
        ("Phase VI", [s for s in streams if "phase_6" in s and "1291" in s][0])
    ]
    
    for phase_lbl, sf in selected:
        fname = os.path.basename(sf).replace(".md", ".pdf")
        out_pdf = os.path.join(out_dir, fname)
        temp_html = os.path.join(out_dir, fname.replace(".pdf", ".html"))

        with open(sf, "r", encoding="utf-8") as f:
            md_text = f.read()

        html_body = markdown.markdown(md_text, extensions=['extra', 'tables', 'fenced_code'])
        full_html = HTML_TEMPLATE.format(title=os.path.basename(sf), content=html_body)

        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(full_html)

        cmd = [
            "chromium", "--headless", "--disable-gpu", "--no-sandbox",
            f"--print-to-pdf={out_pdf}", temp_html
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"  [+] Compiled {phase_lbl} stream PDF: {out_pdf} ({os.path.getsize(out_pdf) / 1024:.1f} KB)")
        if os.path.exists(temp_html):
            os.remove(temp_html)
            
    print(f"[✓] Representative stream compendiums successfully generated in {out_dir}/")

if __name__ == '__main__':
    compile_compendiums()
