"""
Real-time Watcher and Automated Milestone Sealer for the 100,000-Step Century Gym.
Monitors line count until it reaches 100,000, then executes auto_seal_100k_gym.py.
"""

import time
import subprocess
from pathlib import Path

BUFFER_PATH = Path("data/rsi_experience_buffer/massive_100000_gym.jsonl")
TARGET_STEPS = 100000

def watch_and_seal(poll_interval: float = 3.0):
    print("=" * 80)
    print("  IMF 100,000-STEP PROVER GYM COUNTDOWN WATCHER & SEALER (TRACK 3)")
    print(f"  Target Goal: {TARGET_STEPS:,} Machine-Certified Deductions")
    print("=" * 80)

    while True:
        steps = 0
        if BUFFER_PATH.exists():
            with open(BUFFER_PATH, "r") as f:
                for _ in f:
                    steps += 1

        pct = (steps / TARGET_STEPS) * 100.0
        print(f"[*] Current Progress: {steps:,} / {TARGET_STEPS:,} ({pct:.2f}%) | Polling in {poll_interval}s...")

        if steps >= TARGET_STEPS:
            print("\n" + "★" * 80)
            print("  [★] MILESTONE REACHED: 100,000 VERIFIED STEPS COMPLETED!")
            print("★" * 80 + "\n")
            print("[*] Launching Automated Release Sealer...")
            subprocess.run(
                ["python", "scripts/auto_seal_100k_gym.py"],
                check=True
            )
            print("[✓] Century Proof Dataset Successfully Sealed and Certified!")
            break

        time.sleep(poll_interval)

if __name__ == "__main__":
    watch_and_seal()
