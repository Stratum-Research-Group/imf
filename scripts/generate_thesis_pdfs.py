#!/usr/bin/env python3
"""
scripts/generate_thesis_pdfs.py
Renders the three master volumes of 'THE SACRED SANCTUM: FOUNDATIONS OF SOVEREIGN INTELLIGENCE'
into publication-quality PDF documents using Chromium headless with KaTeX and high-DPI full-bleed covers.

Volumes:
1. docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.pdf
2. docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.pdf
3. docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.pdf
"""

import os
import sys
import re
import base64
import subprocess
import shutil
import markdown

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_THESIS = os.path.join(REPO_ROOT, "docs", "thesis")

VOLUMES = [
    {
        "id": "Volume I",
        "vol_num": "v01",
        "src_md": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.md"),
        "out_pdf": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.pdf"),
        "front_cover": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01 Frontcover.jpg"),
        "back_cover": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01 Backcover.jpg"),
        "title": "THE SACRED SANCTUM: Volume I — Dimensional Spaces (d <= 4)",
    },
    {
        "id": "Volume II",
        "vol_num": "v02",
        "src_md": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.md"),
        "out_pdf": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.pdf"),
        "front_cover": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02 Frontcover.jpg"),
        "back_cover": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02 Backcover.jpg"),
        "title": "THE SACRED SANCTUM: Volume II — Higher-Dimensional Spaces (4 < d <= 24)",
    },
    {
        "id": "Volume III",
        "vol_num": "v03",
        "src_md": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.md"),
        "out_pdf": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.pdf"),
        "front_cover": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03 Frontcover.jpg"),
        "back_cover": os.path.join(DOCS_THESIS, "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03 Backcover.jpg"),
        "title": "THE SACRED SANCTUM: Volume III — Transfinite and Ultra-Dimensional Spaces (d -> inf)",
    },
]

CSS_STYLES = """
@page {
    size: 210mm 297mm;
    margin: 0;
}

*, *:before, *:after {
    box-sizing: border-box;
}

html, body {
    margin: 0;
    padding: 0;
    width: 210mm;
    background-color: #ffffff;
    font-family: 'Liberation Serif', 'DejaVu Serif', Georgia, serif;
    font-size: 10.5pt;
    line-height: 1.68;
    color: #1a1a1a;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}

/* Full-bleed covers: strictly edge-to-edge (0 margins), no page numbers */
.cover-page {
    width: 210mm;
    height: 297mm;
    margin: 0;
    padding: 0;
    page-break-before: always;
    page-break-after: always;
    break-before: page;
    break-after: page;
    position: relative;
    overflow: hidden;
    background-color: #000000;
}

.cover-page.front-cover {
    page-break-before: avoid;
    break-before: avoid;
}

.cover-page img {
    position: absolute;
    top: 0;
    left: 0;
    width: 210mm;
    height: 297mm;
    object-fit: cover;
    object-position: center center;
    image-rendering: -webkit-optimize-contrast;
    image-rendering: high-quality;
    display: block;
    margin: 0;
    padding: 0;
}

/* Interior monograph pages: 24mm top/bottom, 22mm left/right */
.content-wrapper {
    box-sizing: border-box;
    width: 210mm;
    max-width: 210mm;
    padding: 24mm 22mm;
    margin: 0 auto;
    word-wrap: break-word;
    overflow-wrap: break-word;
}

/* Typographic Headings with strict pagination rules */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif;
    color: #0f1419;
    page-break-after: avoid !important;
    break-after: avoid-page !important;
    page-break-inside: avoid !important;
    break-inside: avoid !important;
}

h1 {
    font-size: 23pt;
    font-weight: 700;
    border-bottom: 2.5px solid #0969da;
    padding-bottom: 8px;
    margin-top: 2.4em;
    margin-bottom: 0.9em;
    page-break-before: always;
    break-before: page;
}

h1:first-of-type {
    page-break-before: avoid !important;
    break-before: avoid !important;
    margin-top: 0.5em;
}

h2 {
    font-size: 16.5pt;
    font-weight: 700;
    border-bottom: 1.5px solid #d0d7de;
    padding-bottom: 5px;
    margin-top: 2.0em;
    margin-bottom: 0.7em;
    page-break-before: auto;
}

h3 {
    font-size: 13pt;
    font-weight: 600;
    margin-top: 1.6em;
    margin-bottom: 0.5em;
}

h4 {
    font-size: 11pt;
    font-weight: 600;
    margin-top: 1.3em;
    margin-bottom: 0.4em;
}

/* Body paragraphs: justified, elegant line-height, no orphans/widows */
p {
    margin-top: 0.75em;
    margin-bottom: 0.75em;
    text-align: justify;
    hyphens: auto;
    text-indent: 1.5em;
    orphans: 3;
    widows: 3;
}

p:first-of-type, 
h1 + p, h2 + p, h3 + p, h4 + p, h5 + p, h6 + p, 
blockquote + p, pre + p, table + p, hr + p, ul + p, ol + p {
    text-indent: 0;
}

blockquote {
    border-left: 4px solid #0969da;
    margin: 1.6em 0;
    padding: 0.9em 1.5em;
    background-color: #f6f8fa;
    color: #57606a;
    font-style: italic;
    page-break-inside: avoid !important;
    break-inside: avoid !important;
    border-radius: 0 4px 4px 0;
}

/* Lists */
ul, ol {
    margin-top: 0.7em;
    margin-bottom: 0.9em;
    padding-left: 2em;
    orphans: 3;
    widows: 3;
}

li {
    margin-bottom: 0.35em;
    text-align: justify;
}

li::marker {
    color: #0969da;
    font-weight: bold;
}

/* Monospace code and ASCII art blocks */
pre, code {
    font-family: 'Liberation Mono', 'DejaVu Sans Mono', Consolas, monospace;
}

code {
    background-color: #f6f8fa;
    font-size: 8.8pt;
    padding: 2px 5px;
    border-radius: 4px;
    border: 1px solid #e1e4e8;
    word-break: break-word;
}

pre code {
    background: transparent;
    padding: 0;
    border: none;
    font-size: 8.2pt;
    line-height: 1.42;
    white-space: pre-wrap;
    word-wrap: break-word;
}

pre {
    background-color: #f6f8fa;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 12px 14px;
    line-height: 1.42;
    margin: 1.6em 0;
    page-break-inside: avoid !important;
    break-inside: avoid !important;
    overflow-x: hidden;
    max-width: 100%;
}

/* Tables: strictly avoiding page breaks inside rows and blocks */
table {
    border-collapse: collapse;
    width: 100%;
    max-width: 100%;
    margin: 1.8em 0;
    font-size: 9pt;
    line-height: 1.45;
    page-break-inside: avoid !important;
    break-inside: avoid !important;
    table-layout: auto;
}

th, td {
    border: 1px solid #d0d7de;
    padding: 7px 10px;
    text-align: left;
    vertical-align: top;
    word-wrap: break-word;
}

th {
    background-color: #f6f8fa;
    font-weight: 600;
    color: #24292f;
    border-bottom: 2px solid #afb8c1;
}

tr:nth-child(even) {
    background-color: #fafbfc;
}

tr {
    page-break-inside: avoid !important;
    break-inside: avoid !important;
}

thead {
    display: table-header-group;
}

/* Horizontal dividers */
hr {
    border: 0;
    height: 1px;
    background: #d0d7de;
    margin: 2.4em 0;
    page-break-after: avoid;
    break-after: avoid;
}

/* Embedded figures and diagrams */
.content-wrapper img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1.8em auto;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    page-break-inside: avoid !important;
    break-inside: avoid !important;
}

.content-wrapper em {
    color: #4b5563;
}

/* KaTeX equations: strictly avoid breaks inside display math, prevent overflow */
.katex {
    font-size: 1.05em;
}

.katex-display {
    margin: 1.3em 0;
    padding: 0.2em 0;
    overflow-x: auto;
    overflow-y: hidden;
    page-break-inside: avoid !important;
    break-inside: avoid !important;
}
"""

def get_base64_img(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def render_volume_to_pdf(vol):
    src_md = vol["src_md"]
    out_pdf = vol["out_pdf"]
    front_cover = vol["front_cover"]
    back_cover = vol["back_cover"]
    
    if not os.path.exists(src_md):
        print(f"[-] Source Markdown not found: {src_md}")
        return False

    print(f"[*] Processing {vol['id']}: reading {src_md}...")
    with open(src_md, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Strip out any raw cover divs embedded in markdown so we render pixel-perfect edge-to-edge covers
    md_clean = re.sub(r'<div class="cover-page front-cover">[\s\S]*?</div>', '', md_text)
    md_clean = re.sub(r'<div class="cover-page back-cover">[\s\S]*?</div>', '', md_clean)


    # Convert relative markdown image links to high-res inline data URIs
    def embed_local_images(match):
        alt = match.group(1)
        rel_path = match.group(2)
        if rel_path.startswith(('http://', 'https://', 'data:')):
            return match.group(0)
        # resolve relative to src_md dir
        src_dir = os.path.dirname(src_md)
        img_path = os.path.normpath(os.path.join(src_dir, rel_path))
        if os.path.exists(img_path):
            with open(img_path, 'rb') as img_f:
                b64 = base64.b64encode(img_f.read()).decode('utf-8')
            if img_path.endswith('.svg'):
                mime = 'image/svg+xml'
            elif img_path.endswith('.png'):
                mime = 'image/png'
            elif img_path.endswith(('.jpg', '.jpeg')):
                mime = 'image/jpeg'
            else:
                mime = 'application/octet-stream'
            return f'<img src="data:{mime};base64,{b64}" alt="{alt}"/>'
        return match.group(0)

    md_clean = re.sub(r'!\[([^\]]*)\]\(([^\)]+)\)', embed_local_images, md_clean)

    # Convert Markdown to HTML
    html_body = markdown.markdown(
        md_clean,
        extensions=[
            'tables',
            'fenced_code',
            'toc',
            'sane_lists',
        ]
    )

    front_b64 = get_base64_img(front_cover)
    back_b64 = get_base64_img(back_cover)

    # Full HTML with edge-to-edge full bleed covers
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{vol['title']}</title>
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

<div class="cover-page front-cover">
  <img src="data:image/jpeg;base64,{front_b64}" alt="{vol['id']} Front Cover"/>
</div>

<div class="content-wrapper">
{html_body}
</div>

<div class="cover-page back-cover">
  <img src="data:image/jpeg;base64,{back_b64}" alt="{vol['id']} Back Cover"/>
</div>

</body>
</html>
"""

    temp_html = f"/tmp/{vol['vol_num']}_render.html"
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html_doc)

    print(f"[*] Invoking Chromium with high-DPI rasterization for {vol['id']}...")
    cmd = [
        "chromium",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--run-all-compositor-stages-before-draw",
        "--force-device-scale-factor=2",
        "--virtual-time-budget=8000",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={out_pdf}",
        temp_html
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[-] Chromium failed for {vol['id']}: {res.stderr}")
        return False
        
    if os.path.exists(out_pdf):
        sz_mb = os.path.getsize(out_pdf) / (1024 * 1024)
        print(f"[+] Successfully generated high-res PDF: {out_pdf} ({sz_mb:.2f} MB)")
        # Mirror to compiled/
        compiled_pdf = os.path.join(DOCS_THESIS, "compiled", os.path.basename(out_pdf))
        os.makedirs(os.path.dirname(compiled_pdf), exist_ok=True)
        shutil.copyfile(out_pdf, compiled_pdf)
        print(f"    Mirrored to {compiled_pdf}")
        return True
    else:
        print(f"[-] Target PDF was not created: {out_pdf}")
        return False

def main():
    print("=== THE SACRED SANCTUM: HIGH-DPI MASTER THESIS PDF COMPILER ===")
    success = True
    for vol in VOLUMES:
        if not render_volume_to_pdf(vol):
            success = False
            
    if success:
        print("=== ALL THREE MASTER THESIS VOLUMES COMPILED TO HIGH-DPI PDF SUCCESSFULLY ===")
    else:
        print("[-] Some volumes failed to compile to PDF.")
        sys.exit(1)

if __name__ == "__main__":
    main()
