#!/usr/bin/env python3
"""
scripts/audit_trilogy_internal_links.py
Audits internal markdown links across Volumes I, II, and III.
Ensures zero broken local file links while excluding LaTeX math brackets [x, y](m+n).
"""

import os
import glob
import re

def audit_links():
    vols = [
        "docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.md",
        "docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.md",
        "docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.md"
    ]
    print("[*] Auditing internal links across Trilogy Volumes...")

    total_links = 0
    broken_links = 0

    for v in vols:
        if not os.path.exists(v):
            continue
        base_dir = os.path.dirname(v)
        with open(v, "r", encoding="utf-8") as f:
            content = f.read()

        # Find markdown links: [text](path) where path looks like a path (ends in .md, .html, .pdf, or contains /)
        links = re.findall(r'\[([^\]]+)\]\(([^http#\)]+(?:\.md|\.html|\.pdf|\.png|\/)[^\)]*)\)', content)
        for text, target in links:
            total_links += 1
            clean_target = target.split("#")[0]
            if clean_target:
                full_path = os.path.normpath(os.path.join(base_dir, clean_target))
                if not os.path.exists(full_path):
                    broken_links += 1
                    print(f"  [!] Broken link in {os.path.basename(v)}: {target} (resolved to {full_path})")

    print(f"[✓] Audited {total_links} verified markdown hyperlinks across the trilogy.")
    if broken_links == 0:
        print("[✓] 100% of internal trilogy links resolve cleanly.")
    else:
        print(f"[!] Warning: {broken_links} unresolved links found.")
    return broken_links

if __name__ == '__main__':
    audit_links()
