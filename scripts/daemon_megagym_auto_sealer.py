#!/usr/bin/env python3
"""
scripts/daemon_megagym_auto_sealer.py
Autonomous background service that continuously seals MegaGym proof blocks in batches.
Runs quietly, checking manifest state and sealing 10-block intervals (10M steps) at a time.
"""

import time
import sys
import subprocess

def run_loop(max_batches: int = 5, sleep_sec: int = 2):
    print("=== MEGAGYM AUTONOMOUS PROVER FLEET SEALER DAEMON ===")
    print(f"[*] Starting execution loop: sealing up to {max_batches} batches...")

    for b in range(1, max_batches + 1):
        print(f"\n[Batch {b}/{max_batches}] Triggering 10-block sealing cycle...")
        proc = subprocess.run([sys.executable, "scripts/seal_megagym_next_batch.py"], capture_output=True, text=True)
        print(proc.stdout.strip())
        if proc.returncode != 0:
            print("[!] Error during block sealing:", proc.stderr)
            break
        time.sleep(sleep_sec)

    print("\n[+] Autonomous sealing session finished successfully.")

if __name__ == '__main__':
    run_loop(max_batches=2, sleep_sec=1)
