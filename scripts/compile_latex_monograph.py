#!/usr/bin/env python3
"""
scripts/compile_latex_monograph.py
Compiles the Markdown monographs into publication-grade AMS/SIAM LaTeX sources:
- docs/thesis/latex/volume_01.tex
- docs/thesis/latex/volume_02.tex
- docs/thesis/latex/volume_03.tex
Packages into docs/thesis/The_Sacred_Sanctum_LaTeX_Source.zip
"""
import os
import re
import zipfile

LATEX_DIR = "docs/thesis/latex"
os.makedirs(LATEX_DIR, exist_ok=True)

VOLS = [
    ("v01", "Volume I: The Sacred Sanctum of Dimensional Spaces (d <= 4)", "docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.md", "volume_01.tex"),
    ("v02", "Volume II: Higher-Dimensional Spaces (4 < d <= 24)", "docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.md", "volume_02.tex"),
    ("v03", "Volume III: Transfinite and Ultra-Dimensional Spaces (d -> inf)", "docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.md", "volume_03.tex")
]

def md_to_latex(md_content, title):
    # Strip HTML tags
    clean = re.sub(r'<[^>]+>', '', md_content)
    
    # Header replacement
    clean = re.sub(r'^#\s+(.*)', r'\\chapter{\1}', clean, flags=re.M)
    clean = re.sub(r'^##\s+(.*)', r'\\section{\1}', clean, flags=re.M)
    clean = re.sub(r'^###\s+(.*)', r'\\subsection{\1}', clean, flags=re.M)
    clean = re.sub(r'^####\s+(.*)', r'\\subsubsection{\1}', clean, flags=re.M)
    
    # Bold / Italics
    clean = re.sub(r'\*\*(.*?)\*\*', r'\\textbf{\1}', clean)
    clean = re.sub(r'\*(.*?)\*', r'\\textit{\1}', clean)
    
    tex = f"""\\documentclass[11pt,twoside,openright]{{amsbook}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{amsmath,amssymb,amsfonts,amsthm}}
\\usepackage{{geometry}}
\\geometry{{a4paper,top=25mm,bottom=25mm,left=25mm,right=20mm}}
\\usepackage{{graphicx}}
\\usepackage{{hyperref}}
\\usepackage{{listings}}
\\usepackage{{tikz}}
\\usepackage{{tikz-cd}}

\\title{{{title}}}
\\author{{Nicholas Charles Mynhardt \\\\ Stratum Research Group}}
\\date{{November 27, 2026}}

\\begin{{document}}
\\maketitle
\\tableofcontents

{clean}

\\end{{document}}
"""
    return tex

for vcode, vtitle, md_path, tex_file in VOLS:
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()
        tex_content = md_to_latex(md_text, vtitle)
        out_path = os.path.join(LATEX_DIR, tex_file)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(tex_content)
        print(f"[+] Compiled LaTeX source: {out_path}")

# Create zip bundle
zip_path = "docs/thesis/The_Sacred_Sanctum_LaTeX_Source.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for f in os.listdir(LATEX_DIR):
        z.write(os.path.join(LATEX_DIR, f), arcname=f)

print(f"[+] Packaged complete LaTeX source archive to {zip_path}")
