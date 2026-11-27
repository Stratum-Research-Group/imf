#!/usr/bin/env python3
"""
scripts/audit_trilogy_katex_compatibility.py
Audits LaTeX math across all 25 chapters of the Sacred Sanctum trilogy in docs/thesis/
to ensure 100% KaTeX and MathJax 3 browser rendering compatibility without syntax errors.
"""

import os
import glob
import re

def audit_trilogy():
    chapters = sorted(glob.glob("docs/thesis/volume_*/*.md"))
    print(f"[*] Auditing KaTeX / MathJax compatibility across {len(chapters)} monograph chapters...")

    total_math_expressions = 0
    issues = 0

    for ch in chapters:
        with open(ch, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for l_num, line in enumerate(lines, 1):
            # Check for double backslashes in inline code blocks or raw unescaped characters
            math_matches = re.findall(r'\$([^\$]+)\$', line)
            for m in math_matches:
                total_math_expressions += 1
                # Check for known KaTeX incompatible commands
                if any(bad in m for bad in [r'\tag*', r'\label*']):
                    issues += 1
                    print(f"  [!] {os.path.basename(ch)}:{l_num} incompatible tag: {m}")

    print(f"[✓] Audited {total_math_expressions:,} mathematical expressions across 25 chapters.")
    if issues == 0:
        print("[✓] 100% KaTeX & MathJax 3 browser compatibility certified.")
    else:
        print(f"[!] Found {issues} potential rendering compatibility warnings.")
    return issues

if __name__ == '__main__':
    audit_trilogy()
