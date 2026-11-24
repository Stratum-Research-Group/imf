"""
imf/auto_checkpoint_distillation_daemon.py
IMF Continuous Auto-Checkpoint Distillation Daemon.

Monitors data/rsi_experience_buffer/certified_rsi_stream.jsonl.
Whenever 500 new verified theorems accumulate:
1. Loads the latest certified formal experiences.
2. Triggers an online distillation iteration on the student model.
3. Evaluates loss reduction and saves a cryptographically signed checkpoint.
4. Updates dist/student_distillation_checkpoints/manifest.json.
"""

import os
import sys
import time
import json
import hashlib
from pathlib import Path
from typing import Dict, Any

from imf.run_live_rsi_distillation import run_live_distillation

BUFFER_FILE = Path("data/rsi_experience_buffer/certified_rsi_stream.jsonl")
STATE_FILE = Path("dist/student_distillation_checkpoints/auto_distill_state.json")
MANIFEST_FILE = Path("dist/student_distillation_checkpoints/manifest.json")
THRESHOLD = 500


def get_current_experience_count() -> int:
    if not BUFFER_FILE.exists():
        return 0
    count = 0
    with open(BUFFER_FILE, "r") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_distilled_count": 0, "total_distillations": 0}


def save_state(state: Dict[str, Any]):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def run_auto_distillation_check(force: bool = False) -> Dict[str, Any]:
    print("=" * 80)
    print("  IMF AUTO-CHECKPOINT CONTINUOUS DISTILLATION DAEMON")
    print("=" * 80)

    curr_count = get_current_experience_count()
    state = load_state()
    last_count = state.get("last_distilled_count", 0)
    delta = curr_count - last_count

    print(f"Current Certified Theorems: {curr_count}")
    print(f"Last Distilled Theorem Count: {last_count} (Delta: {delta} / Threshold: {THRESHOLD})")

    if delta >= THRESHOLD or force:
        print(f"\n[+] Threshold reached! Running automated student distillation pass...")
        metrics = run_live_distillation(steps=20)
        
        state["last_distilled_count"] = curr_count
        state["total_distillations"] = state.get("total_distillations", 0) + 1
        state["last_run_timestamp"] = time.time()
        state["last_metrics"] = metrics
        save_state(state)

        # Update manifest
        manifest = []
        if MANIFEST_FILE.exists():
            try:
                with open(MANIFEST_FILE, "r") as f:
                    manifest = json.load(f)
            except Exception:
                pass
        manifest.append({
            "distillation_id": state["total_distillations"],
            "theorems_used": curr_count,
            "loss_reduction_pct": metrics.get("loss_reduction_pct", 0.0),
            "checkpoint": metrics.get("checkpoint"),
            "timestamp": time.time()
        })
        with open(MANIFEST_FILE, "w") as f:
            json.dump(manifest, f, indent=2)

        print(f"\n[✓] Automated distillation checkpoint cycle completed successfully.")
        return {"status": "DISTILLED", "metrics": metrics}
    else:
        print(f"\n[i] Accumulating experiences: {delta} / {THRESHOLD} steps to next auto-checkpoint.")
        return {"status": "WAITING", "delta": delta, "threshold": THRESHOLD}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force distillation pass regardless of count")
    args = parser.parse_args()
    run_auto_distillation_check(force=args.force)
