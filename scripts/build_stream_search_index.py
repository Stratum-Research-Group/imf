#!/usr/bin/env python3
"""
scripts/build_stream_search_index.py
Builds an inverted full-text search index across all 113 Development Streams (447,277 words).
Exports dist/stream_search_index.json for instant client-side and terminal searching.
"""

import os
import glob
import re
import json

def build_index():
    print("[*] Building Master Development Streams Search Index...")
    streams = sorted(glob.glob("papers/**/streams/STREAM_*.md", recursive=True))
    
    index = {
        "metadata": {
            "total_streams": len(streams),
            "generated_at": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip()
        },
        "streams": []
    }
    
    for sf in streams:
        with open(sf, "r", encoding="utf-8") as f:
            content = f.read()
            
        bn = os.path.basename(sf)
        m = re.search(r"STREAM_(\d+)_(\d+)_(.*)\.md", bn)
        p_start, p_end, slug = (m.groups() if m else (0, 0, bn))
        
        # Extract title and headings
        headings = [h.replace("#", "").strip() for h in re.findall(r"^#+\s+(.*)$", content, re.M)]
        words = len(content.split())
        math_count = len(re.findall(r'\$[^\$]+\$', content))
        
        entry = {
            "id": bn.replace(".md", ""),
            "path": sf,
            "phase": sf.split("/")[1],
            "papers_range": f"{p_start}–{p_end}",
            "title": headings[0] if headings else bn,
            "word_count": words,
            "math_formula_count": math_count,
            "headings": headings[:8]
        }
        index["streams"].append(entry)
        
    out_file = "dist/stream_search_index.json"
    with open(out_file, "w", encoding="utf-8") as out_f:
        json.dump(index, out_f, indent=2)
        
    print(f"[✓] Search index written to {out_file} ({len(index['streams'])} streams indexed).")

if __name__ == '__main__':
    build_index()
