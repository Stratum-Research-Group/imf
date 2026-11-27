#!/usr/bin/env python3
"""
scripts/compile_papers_corpus_pdfs.py
Batch PDF compiler for the 1,301 papers in papers/.
Generates sample batch PDFs for flagship treatises and provides unified orchestration.
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

def compile_flagship_papers():
    flagship = [
        "papers/phase_1_core_architecture/01_savg_lie_algebraic_memory_splitting.md",
        "papers/phase_1_core_architecture/06_the_imf_omni_block.md",
        "papers/phase_6_blackwell_kernels_and_dma_engines/1301_the_one_billion_certified_proof_steps_milestone_sovereign_sub_bit_fleet_architecture_99_polytope_activation_sparsity_and_chromatic_foundations.md"
    ]

    out_dir = "dist/papers_pdf_archive"
    os.makedirs(out_dir, exist_ok=True)

    for p in flagship:
        if not os.path.exists(p):
            continue
        fname = os.path.basename(p).replace('.md', '.pdf')
        out_pdf = os.path.join(out_dir, fname)
        temp_html = os.path.join(out_dir, fname.replace('.pdf', '.html'))

        with open(p, 'r', encoding='utf-8') as f:
            md_text = f.read()

        html_body = markdown.markdown(md_text, extensions=['extra', 'tables', 'fenced_code'])
        full_html = HTML_TEMPLATE.format(title=os.path.basename(p), content=html_body)

        with open(temp_html, 'w', encoding='utf-8') as f:
            f.write(full_html)

        # Compile via chromium headless
        cmd = [
            "chromium", "--headless", "--disable-gpu", "--no-sandbox",
            f"--print-to-pdf={out_pdf}", temp_html
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[+] Compiled flagship paper PDF: {out_pdf} ({os.path.getsize(out_pdf) / 1024:.1f} KB)")
        if os.path.exists(temp_html):
            os.remove(temp_html)

if __name__ == '__main__':
    compile_flagship_papers()
