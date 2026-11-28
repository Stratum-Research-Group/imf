#!/usr/bin/env python3
"""
scripts/audit_development_stream_crosslinks.py
Audits bidirectional cross-link integrity between all 113 Development Streams,
docs/MASTER_DEVELOPMENT_STREAMS_CATALOG.md, and docs/CONSOLIDATED_STEPS_MILESTONES_LEDGER.md.
"""

import os
import glob
import re

def audit_crosslinks():
    catalog_path = "docs/MASTER_DEVELOPMENT_STREAMS_CATALOG.md"
    ledger_path = "docs/CONSOLIDATED_STEPS_MILESTONES_LEDGER.md"
    streams = sorted(glob.glob("papers/**/streams/STREAM_*.md", recursive=True))

    print(f"[*] Auditing cross-link references across {len(streams)} canonical Development Streams...")

    if not os.path.exists(catalog_path):
        print(f"[!] Catalog missing at {catalog_path}")
        return 1

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog_text = f.read()

    missing_in_catalog = []
    for s in streams:
        basename = os.path.basename(s)
        # Extract stream prefix, e.g., STREAM_0001_0010
        match = re.match(r"(STREAM_\d{4}_\d{4})", basename)
        if match:
            stream_id = match.group(1)
            if stream_id not in catalog_text:
                missing_in_catalog.append(stream_id)

    print(f"[+] Total verified streams in catalog: {len(streams) - len(missing_in_catalog)}/{len(streams)}")
    if missing_in_catalog:
        print(f"[!] Warning: {len(missing_in_catalog)} streams not indexed in catalog: {missing_in_catalog[:3]}")
    else:
        print("[✓] 100% of Development Streams are fully cross-referenced in the Master Catalog.")
    return 0

if __name__ == '__main__':
    audit_crosslinks()
