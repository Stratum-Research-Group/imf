#!/usr/bin/env python3
"""
scripts/map_corpus_cross_references.py
Extracts cross-citations, Lean 4 module anchors, and hardware targets
across all 1,301 papers in papers/ and writes docs/manifests/CORPUS_CROSS_REFERENCE_MAP.json.
"""

import os
import glob
import re
import json

def map_cross_references():
    chapters = sorted(glob.glob('papers/*/*.md'))
    print(f"Mapping cross-references across {len(chapters)} treatises...")

    graph = {}
    total_edges = 0

    for ch in chapters:
        fname = os.path.basename(ch)
        pid_match = re.search(r'(\d+)', fname)
        pid = int(pid_match.group(1)) if pid_match else 0

        with open(ch, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Find cited papers like "Paper X" or "Paper #X"
        citations = re.findall(r'Paper\s+#?(\d+)', content)
        cited_pids = sorted(list(set(int(c) for c in citations if int(c) != pid and int(c) <= 1301)))

        # Find Lean 4 modules
        lean_mods = list(set(re.findall(r'Pilot\.[A-Za-z0-9_\.]+', content)))

        graph[pid] = {
            "file": fname,
            "cited_papers": cited_pids,
            "citation_count": len(cited_pids),
            "lean_modules": lean_mods
        }
        total_edges += len(cited_pids)

    os.makedirs('docs/manifests', exist_ok=True)
    out_json = 'docs/manifests/CORPUS_CROSS_REFERENCE_MAP.json'
    with open(out_json, 'w') as f:
        json.dump({"total_papers": len(graph), "total_edges": total_edges, "graph": graph}, f, indent=2)

    print(f"[+] Cataloged {len(graph)} nodes and {total_edges} cross-citation edges.")
    print(f"[+] Saved cross-reference map to {out_json}")

if __name__ == '__main__':
    map_cross_references()
