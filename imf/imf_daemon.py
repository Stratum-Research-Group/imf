"""
imf/imf_daemon.py
Autonomous background self-improvement daemon for IMF.
Continuously runs formal Lean 4 RSI loops, verifies invariants, and logs progress.
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from imf.eth_lean_recursive_improver import ETHLeanRecursiveImprover


class IMFDaemon:
    def __init__(self, log_dir: str = "logs/daemon"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.improver = ETHLeanRecursiveImprover()
        self.status_file = self.log_dir / "daemon_status.json"

    def run_iterations(self, num_iterations: int = 5, sleep_sec: float = 1.0):
        print(f"[*] Starting IMF Autonomous RSI Daemon (PID: {os.getpid()})")
        print(f"[*] Logging state to: {self.status_file}")

        total_discovered = 0
        for it in range(1, num_iterations + 1):
            gen_seed = it + 100  # Start beyond the base 100 generations
            print(f"\n[Daemon Cycle {it}/{num_iterations}] Exploring Generation {gen_seed} ...")

            candidates = self.improver.generate_candidate_theorems(generation_seed=gen_seed)
            cycle_verified = 0

            for cand in candidates:
                ok, err = self.improver.verify_lean_snippet(cand["code"])
                if ok:
                    cycle_verified += 1
                    total_discovered += 1
                    print(f"  [✓] Verified in Lean 4: {cand['name']}")
                else:
                    print(f"  [✗] Failed: {cand['name']} ({err[:40]})")

            status = {
                "iteration": it,
                "current_gen": gen_seed,
                "cycle_verified": cycle_verified,
                "total_verified": total_discovered,
                "timestamp": time.time(),
                "status": "RUNNING",
            }
            self.status_file.write_text(json.dumps(status, indent=2))
            time.sleep(sleep_sec)

        print("\n[✓] IMF Autonomous Daemon finished iterations cleanly.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IMF Autonomous Daemon")
    parser.add_argument("--iterations", type=int, default=3, help="Number of exploration cycles")
    parser.add_argument("--sleep", type=float, default=0.5, help="Sleep interval between cycles")
    args = parser.parse_args()

    daemon = IMFDaemon()
    daemon.run_iterations(num_iterations=args.iterations, sleep_sec=args.sleep)
