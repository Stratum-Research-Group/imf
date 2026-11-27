#!/usr/bin/env python3
"""
scripts/audit_lean_theorem_deduplication.py
Audits all 497 theorems in lean_pilot/ to detect redundant or identical
lemma variants and builds an optimization report in benchmark_results/.
"""

import os
import glob
import re
import json

def audit_theorems():
    lean_files = sorted(glob.glob('lean_pilot/Pilot/**/*.lean', recursive=True))
    print(f"Auditing theorem deduplication across {len(lean_files)} modules...")

    theorem_sigs = {}
    duplicates = []

    for lf in lean_files:
        mod = os.path.relpath(lf, 'lean_pilot')
        with open(lf, 'r', encoding='utf-8') as f:
            content = f.read()

        matches = re.findall(r'(theorem|lemma)\s+([A-Za-z0-9_\.]+)\s*:\s*([^:=]+)', content)
        for kind, name, sig in matches:
            norm_sig = re.sub(r'\s+', ' ', sig).strip()
            if norm_sig in theorem_sigs:
                duplicates.append({
                    "original": theorem_sigs[norm_sig],
                    "duplicate": f"{mod}::{name}",
                    "signature": norm_sig
                })
            else:
                theorem_sigs[norm_sig] = f"{mod}::{name}"

    print(f"[+] Total unique theorem types: {len(theorem_sigs)}")
    print(f"[+] Redundant / structural duplicates discovered: {len(duplicates)}")

    os.makedirs('benchmark_results', exist_ok=True)
    report_path = 'benchmark_results/lean_deduplication_report.json'
    with open(report_path, 'w') as f:
        json.dump({
            "total_theorems": len(theorem_sigs) + len(duplicates),
            "unique_signatures": len(theorem_sigs),
            "duplicates_count": len(duplicates),
            "duplicates": duplicates[:20]
        }, f, indent=2)

    print(f"[+] Wrote deduplication audit report to {report_path}")

if __name__ == '__main__':
    audit_theorems()
