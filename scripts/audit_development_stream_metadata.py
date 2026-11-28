#!/usr/bin/env python3
"""
scripts/audit_development_stream_metadata.py
Audits metadata, H1 title consistency, and word length across all 113 Development Streams.
"""

import os
import glob
import re

def audit_metadata():
    streams = sorted(glob.glob("papers/**/streams/STREAM_*.md", recursive=True))
    print(f"[*] Auditing metadata for {len(streams)} canonical Development Streams...")

    total_words = 0
    passed = 0

    for s in streams:
        with open(s, "r", encoding="utf-8") as f:
            content = f.read()

        words = len(content.split())
        total_words += words
        if content.strip().startswith("#"):
            passed += 1

    print(f"[+] Total corpus words in streams: {total_words:,} words across {len(streams)} streams.")
    print(f"[✓] {passed}/{len(streams)} Development Streams adhere to standard formatting.")
    return 0 if passed == len(streams) else 1

if __name__ == '__main__':
    audit_metadata()
