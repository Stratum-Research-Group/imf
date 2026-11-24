"""
imf/daemon_parquet_syncer.py
Continuous Parquet Lake Auto-Sync Daemon.
Monitors dist/gym_32b_corpus for newly sealed .tar.zst blocks,
streams sample records into partitioned DuckDB/Parquet storage in real time,
and continuously refreshes the mission control columnar metrics.
"""

import os
import sys
import time
import json
from pathlib import Path
from imf.parquet_telemetry_streamer import export_block_to_parquet
import duckdb

CORPUS_DIR = Path("dist/gym_32b_corpus")
PARQUET_DIR = Path("dist/parquet_lake")
MANIFEST_REPORT = Path("dist/PARQUET_TELEMETRY_INDEX_REPORT.json")


def sync_new_blocks():
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    all_blocks = sorted(list(CORPUS_DIR.glob("block_*.tar.zst")))
    
    synced_blocks = []
    for b in all_blocks:
        b_name = b.stem.replace(".tar", "")
        p_path = PARQUET_DIR / f"{b_name}.parquet"
        if not p_path.exists():
            print(f"[*] New block detected: {b_name}, generating Parquet partition...")
            try:
                export_block_to_parquet(b, PARQUET_DIR, max_sample=10000)
                synced_blocks.append(b_name)
            except Exception as e:
                print(f"[!] Error exporting {b_name}: {e}")

    # Re-run summary
    parquet_glob = str(PARQUET_DIR / "*.parquet")
    con = duckdb.connect()
    try:
        df_summary = con.execute(f"""
            SELECT 
                block_id, 
                COUNT(*) as steps, 
                AVG(loss) as avg_loss, 
                AVG(perplexity) as avg_ppl, 
                SUM(axioms_count) as total_axioms
            FROM '{parquet_glob}'
            GROUP BY block_id
            ORDER BY block_id
        """).fetchall()

        total_steps = sum(row[1] for row in df_summary)
        total_axioms = sum(row[4] for row in df_summary)
        losses = [row[2] for row in df_summary]
        
        manifest = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "lake_path": str(PARQUET_DIR),
            "total_parquet_files": len(list(PARQUET_DIR.glob("*.parquet"))),
            "sampled_records": total_steps,
            "average_loss": sum(losses) / len(losses) if losses else 0.0,
            "total_axioms": total_axioms,
            "recently_synced": synced_blocks
        }
        with open(MANIFEST_REPORT, "w") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"[!] Summary aggregation error: {e}")

    return len(synced_blocks)


def run_daemon(poll_interval: float = 10.0, max_iterations: int = 1):
    print("=" * 80)
    print("  IMF CONTINUOUS PARQUET LAKE AUTO-SYNC DAEMON")
    print(f"  Watching: {CORPUS_DIR} -> {PARQUET_DIR}")
    print("=" * 80)

    for i in range(max_iterations):
        n = sync_new_blocks()
        if n > 0:
            print(f"[✓] Iteration {i+1}: Synced {n} new block(s) into Parquet Lake.")
        else:
            print(f"[*] Iteration {i+1}: Parquet lake up to date.")
        if i + 1 < max_iterations:
            time.sleep(poll_interval)


if __name__ == "__main__":
    max_iters = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run_daemon(max_iterations=max_iters)
