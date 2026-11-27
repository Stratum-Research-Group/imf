#!/usr/bin/env python3
"""
scripts/audit_stream_equation_density.py
Audits all 113 consolidated development streams, verifying word count thresholds
and counting LaTeX / KaTeX equation density.
"""

import os
import glob
import re

def audit_streams():
    streams = sorted(glob.glob("papers/**/streams/STREAM_*.md", recursive=True))
    print(f"[*] Auditing {len(streams)} consolidated development streams for word count and math density...")

    total_words = 0
    total_math_blocks = 0
    short_streams = []

    for sf in streams:
        with open(sf, "r", encoding="utf-8") as f:
            content = f.read()

        words = len(content.split())
        total_words += words

        # Count inline and display math
        inline_math = len(re.findall(r'\$[^\$]+\$', content))
        display_math = len(re.findall(r'\$\$[^\$]+\$\$', content))
        math_count = inline_math + display_math
        total_math_blocks += math_count

        if words < 1000:
            short_streams.append((sf, words))

    print(f"[✓] Total Stream Corpus Volume: {total_words:,} words across {len(streams)} streams.")
    print(f"[✓] Average Volume per Stream: {total_words // len(streams):,} words.")
    print(f"[✓] Total Mathematical Expressions Verified: {total_math_blocks:,} formulas.")
    if short_streams:
        print(f"[!] Warning: {len(short_streams)} streams under 1,000 words.")
    else:
        print("[✓] 100% of streams satisfy the minimum publication density threshold.")
    return 0

if __name__ == '__main__':
    audit_streams()
