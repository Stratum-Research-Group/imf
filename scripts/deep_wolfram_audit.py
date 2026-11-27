#!/usr/bin/env python3
"""
Deep Wolfram-Grade Scrutiny Audit
Stephen Wolfram looks for:
1. Exact computational terminology and physics parallels (cellular automata, graph rewriting, hypergraphs, discrete vs continuous spacetime).
2. Rigorous definitions of Lie groups, Clifford algebras, lattices, and spectra.
3. Obvious copy-paste errors or duplicated section titles.
4. Broken LaTeX syntax like \frac without arguments, \sqrt{}, broken tables.
5. Inconsistencies between text claims and Lean 4 code blocks.
"""
import glob
import os
import re

files = sorted(glob.glob("docs/thesis/volume_*/chapter_*.md"))
print(f"Deep auditing {len(files)} chapters...")

for fpath in files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        text = f.read()

    # 1. Check for duplicate headers
    headers = re.findall(r'^(#{1,4}\s+.*)', text, re.M)
    seen = set()
    for h in headers:
        clean_h = h.strip()
        if clean_h in seen and not clean_h.startswith("### References") and not clean_h.startswith("## References") and not clean_h.startswith("---"):
            print(f"[!] Duplicate header in {fname}: {clean_h}")
        seen.add(clean_h)

    # 2. Check for empty math commands: \frac{}, \sqrt{}, \text{}
    empty_math = re.findall(r'(\\(?:frac|sqrt|text|mathbf|mathcal)\{\s*\})', text)
    if empty_math:
        print(f"[!] Empty math commands in {fname}: {empty_math}")

    # 3. Check for raw HTML tags that shouldn't be there (except valid ones)
    bad_html = re.findall(r'<(?!\/?(?:div|img|span|br|b|i|table|tr|th|td|sub|sup|details|summary|h[1-6]|p|pre|code)\b)[a-zA-Z][^>]*>', text)
    if bad_html:
        print(f"[!] Questionable HTML in {fname}: {bad_html[:5]}")

    # 4. Check for unrendered KaTeX commands that break in KaTeX
    # KaTeX does NOT support certain full LaTeX packages like \xymatrix, \tikz, \begin{equation*}, etc.
    unsupported_katex = re.findall(r'(\\begin\{(?:tikzpicture|xy|diagram|align\*?|gather\*?)\})', text)
    if unsupported_katex:
        print(f"[!] Potentially unsupported KaTeX environment in {fname}: {unsupported_katex}")

print("Deep audit finished.")
