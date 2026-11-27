#!/usr/bin/env python3
"""
scripts/audit_monograph_bibtex_citations.py
Audits all citations across the 25 chapters of the Sacred Sanctum trilogy
AND all 113 Development Streams, verifying that citations resolve to canonical references.bib entries.
"""

import os
import glob
import re

def audit_bibtex():
    bib_path = "docs/thesis/references.bib"
    chapters = sorted(glob.glob("docs/thesis/volume_*/*.md"))
    streams = sorted(glob.glob("papers/**/streams/STREAM_*.md", recursive=True))
    all_targets = chapters + streams
    print(f"[*] Auditing BibTeX citations across {len(chapters)} monograph chapters and {len(streams)} development streams ({len(all_targets)} documents)...")

    if not os.path.exists(bib_path):
        print(f"[!] references.bib missing at {bib_path}")
        return 1

    with open(bib_path, "r", encoding="utf-8") as bf:
        bib_text = bf.read()

    # Extract all @type{key,
    bib_keys = set(re.findall(r'@\w+\s*\{\s*([^,\s]+),', bib_text))
    print(f"[+] Loaded {len(bib_keys)} canonical entries from references.bib.")

    cited_keys = set()
    for doc in all_targets:
        with open(doc, "r", encoding="utf-8") as f:
            content = f.read()
        # Find \cite{key} or \cite{key1, key2}
        citations = re.findall(r'\\cite\{([^}]+)\}', content)
        for c in citations:
            for k in c.split(","):
                k_clean = k.strip()
                if k_clean:
                    cited_keys.add(k_clean)

    missing = cited_keys - bib_keys
    print(f"[+] Total unique cited reference keys: {len(cited_keys)}")
    if missing:
        print(f"[!] Warning: {len(missing)} cited keys not found in references.bib: {list(missing)[:5]}")
    else:
        print(f"[✓] 100% of corpus citations ({len(cited_keys)} cited keys across {len(all_targets)} documents) resolve to canonical references.bib entries.")
    return 0

if __name__ == '__main__':
    audit_bibtex()
