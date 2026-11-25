"""
IMF Continuous Parquet Lake Auto-Sync & Super-Compaction Daemon
Automates incremental block sync and triggers 10M super-compaction every 10 blocks.
"""

import os
import glob
import time
import subprocess

PARQUET_LAKE_DIR = "dist/parquet_lake"
COMPACTED_DIR = "dist/parquet_lake/compacted_10m"

def sync_and_check_compaction():
    print("=== Checking Lake Sync & Super-Compaction Status ===")
    res = subprocess.run(["uv", "run", "python", "imf/daemon_parquet_syncer.py"], capture_output=True, text=True)
    print(res.stdout)

    all_blocks = glob.glob(os.path.join(PARQUET_LAKE_DIR, "block_*.parquet"))
    count = len(all_blocks)
    print(f"Total Block Partitions in Lake: {count}")

    # Check if a new 10M boundary has been reached
    compacted_files = glob.glob(os.path.join(COMPACTED_DIR, "*.parquet"))
    expected_super_blocks = count // 10

    if len(compacted_files) < expected_super_blocks:
        print(f"[*] New 10M super-batch detected ({count} blocks). Triggering auto-compactor...")
        res_comp = subprocess.run(["uv", "run", "python", "imf/lake_auto_compactor.py"], capture_output=True, text=True)
        print(res_comp.stdout)
    else:
        print(f"[✓] Super-compaction up-to-date ({len(compacted_files)}/{expected_super_blocks} super-partitions active).")

if __name__ == "__main__":
    sync_and_check_compaction()
