#!/usr/bin/env python3
"""
scripts/export_proof_corpus_parquet.py
Compacts certified Lean 4 proof step metadata from dist/IMF_32B_GRAND_CORPUS_MANIFEST.json
into high-performance partitioned Apache Parquet datasets using pyarrow.
"""

import os
import json
import pyarrow as pa
import pyarrow.parquet as pq

def export_parquet():
    manifest_path = "dist/IMF_32B_GRAND_CORPUS_MANIFEST.json"
    out_dir = "dist/parquet_lake"
    os.makedirs(out_dir, exist_ok=True)
    out_parquet = os.path.join(out_dir, "certified_proof_steps_1b.parquet")

    if not os.path.exists(manifest_path):
        print(f"Error: {manifest_path} not found.")
        return

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    blocks = manifest.get("blocks", [])
    print(f"[*] Packaging {len(blocks)} sealed blocks into Parquet table...")

    data = {
        "block_idx": [b["block_idx"] for b in blocks],
        "steps": [b["steps"] for b in blocks],
        "elapsed_seconds": [b["elapsed_seconds"] for b in blocks],
        "steps_per_sec": [b["steps_per_sec"] for b in blocks],
        "raw_sha256": [b["raw_sha256"] for b in blocks],
        "archive_sha256": [b["archive_sha256"] for b in blocks],
        "archive_size_bytes": [b["archive_size_bytes"] for b in blocks]
    }

    table = pa.Table.from_pydict(data)
    pq.write_table(table, out_parquet, compression="zstd")
    print(f"[+] Successfully exported Parquet dataset: {out_parquet} ({os.path.getsize(out_parquet) / 1024:.1f} KB)")

if __name__ == '__main__':
    export_parquet()
