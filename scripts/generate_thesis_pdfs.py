#!/usr/bin/env python3
"""
scripts/generate_thesis_pdfs.py
Renders the three master volumes of 'THE SACRED SANCTUM: FOUNDATIONS OF SOVEREIGN INTELLIGENCE'
into publication-quality PDF documents using Chromium headless with KaTeX and Pygments syntax highlighting.

Volumes:
1. docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.pdf
2. docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.pdf
3. docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.pdf
"""

import os
import sys
import glob
import subprocess
import markdown

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_THESIS = os.path.join(REPO_ROOT, "docs", "thesis")

VOLUMES = [
    {
        "id": "Volume I",
        "vol_num": "v01",
        "src_md": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.md"),
        "out_pdf": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.pdf"),
        "title": "THE SACRED SANCTUM: Volume I — Dimensional Spaces (d <= 4)",
    },
    {
        "id": "Volume II",
        "vol_num": "v02",
        "src_md": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.md"),
        "out_pdf": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.pdf"),
        "title": "THE SACRED SANCTUM: Volume II — Higher-Dimensional Spaces (4 < d <= 24)",
    },
    {
        "id": "Volume III",
        "vol_num": "v03",
        "src_md": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.md"),
        "out_pdf": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.pdf"),
        "title": "THE SACRED SANCTUM: Volume III — Transfinite and Ultra-Dimensional Spaces (d -> inf)",
    },
]

CSS_STYLES = """
@page {
    size: A4;
    margin: 20mm 15mm 20mm 15mm;
    @bottom-center {
        content: counter(page);
        font-family: 'Liberation Sans', sans-serif;
        font-size: 8.5pt;
        color: #555;
    }
}

body {
    font-family: 'Liberation Serif', 'DejaVu Serif', Georgia, serif;
    font-size: 10.5pt;
    line-height: 1.55;
    color: #1a1a1a;
    background-color: #ffffff;
    max-width: 100%;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif;
    font-weight: 700;
    color: #0f1419;
    margin-top: 1.4em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
    break-after: avoid;
}

h1 {
    font-size: 22pt;
    border-bottom: 2px solid #0969da;
    padding-bottom: 6px;
    margin-top: 1.8em;
}

h2 {
    font-size: 16pt;
    border-bottom: 1px solid #d0d7de;
    padding-bottom: 4px;
}

h3 {
    font-size: 13pt;
}

h4 {
    font-size: 11pt;
}

p {
    margin-top: 0.6em;
    margin-bottom: 0.6em;
    text-align: justify;
    hyphens: auto;
}

blockquote {
    border-left: 4px solid #0969da;
    margin: 1.2em 0;
    padding: 0.6em 1.2em;
    background-color: #f6f8fa;
    color: #57606a;
    font-style: italic;
    page-break-inside: avoid;
}

pre, code {
    font-family: 'Liberation Mono', 'DejaVu Sans Mono', Consolas, monospace;
    font-size: 8.5pt;
}

code {
    background-color: #f6f8fa;
    padding: 2px 5px;
    border-radius: 4px;
    border: 1px solid #e1e4e8;
}

pre code {
    background: transparent;
    padding: 0;
    border: none;
}

pre {
    background-color: #f6f8fa;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 10px 14px;
    overflow-x: auto;
    line-height: 1.4;
    margin: 1.2em 0;
    page-break-inside: avoid;
    break-inside: avoid;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 1.4em 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
    break-inside: avoid;
}

th, td {
    border: 1px solid #d0d7de;
    padding: 6px 10px;
    text-align: left;
}

th {
    background-color: #f6f8fa;
    font-weight: 600;
}

tr:nth-child(even) {
    background-color: #fafbfc;
}

hr {
    border: 0;
    height: 1px;
    background: #d0d7de;
    margin: 2em 0;
}

img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1.5em auto;
    page-break-inside: avoid;
}

.cover-page {
    page-break-after: always;
    break-after: page;
    text-align: center;
    margin: 0;
    padding: 0;
}

.cover-page img {
    max-height: 95vh;
    max-width: 95vw;
    object-fit: contain;
    margin: auto;
}

.katex {
    font-size: 1.05em;
}

.katex-display {
    margin: 1em 0;
    overflow-x: auto;
    overflow-y: hidden;
}
"""

def render_volume_to_pdf(vol):
    src_md = vol["src_md"]
    out_pdf = vol["out_pdf"]
    
    if not os.path.exists(src_md):
        print(f"[-] Source Markdown not found: {src_md}")
        return False

    print(f"[*] Processing {vol['id']}: reading {src_md}...")
    with open(src_md, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Convert Markdown to HTML
    html_body = markdown.markdown(
        md_text,
        extensions=[
            'tables',
            'fenced_code',
            'toc',
            'sane_lists',
        ]
    )

    # Full standalone HTML with KaTeX math rendering and cover handling
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{vol['title']}</title>
<base href="{DOCS_THESIS}/"/>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css"/>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"
    onload="renderMathInElement(document.body, {{
        delimiters: [
            {{left: '$$', right: '$$', display: true}},
            {{left: '$', right: '$', display: false}}
        ],
        throwOnError: false
    }});"></script>
<style>
{CSS_STYLES}
</style>
</head>
<body>
{html_body}
</body>
</html>
"""

    temp_html = f"/tmp/{vol['vol_num']}_render.html"
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html_doc)

    print(f"[*] Invoking Chromium to print {vol['id']} to PDF...")
    cmd = [
        "chromium",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=6000",
        f"--print-to-pdf={out_pdf}",
        temp_html
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[-] Chromium failed for {vol['id']}: {res.stderr}")
        return False
        
    if os.path.exists(out_pdf):
        sz_mb = os.path.getsize(out_pdf) / (1024 * 1024)
        print(f"[+] Successfully generated {out_pdf} ({sz_mb:.2f} MB)")
        # Also copy to compiled/
        compiled_pdf = os.path.join(DOCS_THESIS, "compiled", os.path.basename(out_pdf))
        os.makedirs(os.path.dirname(compiled_pdf), exist_ok=True)
        import shutil
        shutil.copyfile(out_pdf, compiled_pdf)
        print(f"    Mirrored to {compiled_pdf}")
        return True
    else:
        print(f"[-] Target PDF was not created: {out_pdf}")
        return False

def main():
    print("=== THE SACRED SANCTUM: MASTER THESIS PDF COMPILER ===")
    success = True
    for vol in VOLUMES:
        if not render_volume_to_pdf(vol):
            success = False
            
    if success:
        print("=== ALL THREE MASTER THESIS VOLUMES COMPILED TO PDF SUCCESSFULLY ===")
    else:
        print("[-] Some volumes failed to compile to PDF.")
        sys.exit(1)

if __name__ == "__main__":
    main()
