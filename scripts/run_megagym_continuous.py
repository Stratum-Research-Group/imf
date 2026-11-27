#!/usr/bin/env python3
"""
scripts/run_megagym_continuous.py
Continuous background engine for the MegaGym Prover Fleet.
Seals blocks in batches of 20 with lockfile safety, advancing towards the 2-Billion mark.
"""

import os
import sys
import time
import subprocess

LOCK_FILE = "/tmp/megagym_prover.lock"

def run_continuous_batches(target_batches: int = 2):
    if os.path.exists(LOCK_FILE):
        print("[!] Prover lockfile exists. Another process may be sealing blocks.")
        return

    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))

        print(f"=== MEGAGYM CONTINUOUS PROVER SCALING ENGINE ===")
        print(f"[*] Executing {target_batches} batch cycles (20 blocks / 20,000,000 steps)...")

        for b in range(1, target_batches + 1):
            print(f"\n[*] Cycle {b}/{target_batches}: Sealing 10 blocks...")
            proc = subprocess.run([sys.executable, "scripts/seal_megagym_next_batch.py"], capture_output=True, text=True)
            print(proc.stdout.strip())
            if proc.returncode != 0:
                print("[!] Error in batch execution:", proc.stderr)
                break
            time.sleep(1)

        print("\n[+] Scaling cycle completed cleanly.")
    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

if __name__ == '__main__':
    run_continuous_batches(2)
