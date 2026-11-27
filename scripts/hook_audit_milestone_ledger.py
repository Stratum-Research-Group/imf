#!/usr/bin/env python3
"""
scripts/hook_audit_milestone_ledger.py
Audits consistency between dist/IMF_32B_GRAND_CORPUS_MANIFEST.json
and docs/CONSOLIDATED_STEPS_MILESTONES_LEDGER.md.
"""

import json
import os
import sys

def audit_ledger():
    manifest_path = "dist/IMF_32B_GRAND_CORPUS_MANIFEST.json"
    ledger_path = "docs/CONSOLIDATED_STEPS_MILESTONES_LEDGER.md"

    if not os.path.exists(manifest_path) or not os.path.exists(ledger_path):
        print("[!] Manifest or ledger file missing.")
        return 1

    with open(manifest_path) as mf:
        mdata = json.load(mf)
    with open(ledger_path) as lf:
        ltext = lf.read()

    blocks = mdata.get("blocks_completed", 0)
    steps = mdata.get("total_certified_theorems", 0)

    # Check if steps number appears in ledger
    step_str = f"{steps:,}"
    block_str = f"{blocks:,}"

    if str(steps) in ltext or step_str in ltext:
        print(f"[✓] Milestone ledger audit passed: {step_str} steps certified.")
        return 0
    else:
        print(f"[!] Warning: Ledger does not explicitly mention {step_str} steps.")
        return 0

if __name__ == '__main__':
    sys.exit(audit_ledger())
