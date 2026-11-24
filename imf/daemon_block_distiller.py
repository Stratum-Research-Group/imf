"""
imf/daemon_block_distiller.py
Continuous Autonomous Checkpoint Distiller Daemon.
Watches dist/gym_32b_corpus/ for newly completed block archives and automatically
triggers an online distillation micro-epoch with zero human intervention.
"""

import time
import json
from pathlib import Path
from imf.auto_trigger_distillation_hook import execute_block_sealed_hook

class AutonomousBlockDistiller:
    def __init__(self, corpus_dir: str = "dist/gym_32b_corpus", state_file: str = "dist/.distiller_last_block.json"):
        self.corpus_dir = Path(corpus_dir)
        self.state_file = Path(state_file)
        self.last_block = self._load_last_block()

    def _load_last_block(self) -> int:
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f).get("last_processed_block", 0)
            except Exception:
                pass
        return 0

    def _save_last_block(self, block_id: int):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump({"last_processed_block": block_id, "timestamp": time.time()}, f)

    def scan_and_distill(self, max_runs: int = 1) -> int:
        archives = sorted(list(self.corpus_dir.glob("block_*.tar.zst")))
        if not archives:
            return 0

        latest_arch = archives[-1]
        try:
            # extract block index from name (block_00044.tar.zst -> 44)
            latest_idx = int(latest_arch.stem.split(".")[0].replace("block_", ""))
        except Exception:
            return 0

        processed = 0
        if latest_idx > self.last_block:
            print(f"[*] New block detected: Block {latest_idx:05d} (Previous: {self.last_block:05d})")
            execute_block_sealed_hook(latest_idx)
            self._save_last_block(latest_idx)
            self.last_block = latest_idx
            processed += 1
        else:
            print(f"[*] Distiller up to date. Latest Block: {latest_idx:05d}")

        return processed

def run_distiller_smoke_test():
    print("=" * 80)
    print("  IMF AUTONOMOUS BLOCK DISTILLER DAEMON SMOKE-TEST")
    print("=" * 80)

    distiller = AutonomousBlockDistiller()
    count = distiller.scan_and_distill(max_runs=1)
    print(f"[✓] Distiller check completed. Processed: {count} new blocks.")
    print("=" * 80)

if __name__ == "__main__":
    run_distiller_smoke_test()
