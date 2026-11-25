"""
scripts/ingest_theorems_to_lake.py
Automated CLI tool for ingesting formal theorem records into dist/parquet_lake/.
Enforces:
1. Statement SHA-256 hash deduplication against existing lake blocks.
2. Axiom purity filter (rejects entries with non-standard external axioms).
3. Auto-partitioning into rolling block_XXXXX.parquet files (10,000 theorems per partition block).
"""

import os
import sys
import json
import glob
import hashlib
import argparse
from pathlib import Path
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


def compute_stmt_hash(stmt: str) -> str:
    return hashlib.sha256(stmt.strip().encode("utf-8")).hexdigest()[:16]


def get_existing_hashes(lake_dir: str) -> set:
    parquet_files = glob.glob(os.path.join(lake_dir, "block_*.parquet"))
    if not parquet_files:
        return set()
    con = duckdb.connect()
    res = con.execute(f"SELECT DISTINCT stmt_hash FROM '{lake_dir}/block_*.parquet'").fetchall()
    return {r[0] for r in res}


def get_next_block_index(lake_dir: str) -> int:
    parquet_files = sorted(glob.glob(os.path.join(lake_dir, "block_*.parquet")))
    if not parquet_files:
        return 1
    last_file = os.path.basename(parquet_files[-1])
    # block_00003.parquet
    try:
        idx_str = last_file.split("_")[1].split(".")[0]
        return int(idx_str) + 1
    except Exception:
        return len(parquet_files) + 1


def ingest_records(input_path: str, lake_dir: str = "dist/parquet_lake", block_size: int = 10000):
    print("=" * 80)
    print("  IMF THEOREM PARQUET LAKE AUTOMATED INGESTION CLI")
    print(f"  Source Input:    {input_path}")
    print(f"  Target Lake Dir: {lake_dir}")
    print("=" * 80)

    os.makedirs(lake_dir, exist_ok=True)
    existing_hashes = get_existing_hashes(lake_dir)
    print(f"[*] Loaded {len(existing_hashes):,} existing unique theorem hashes from lake.")

    # Read records from JSONL
    new_records = []
    skipped_duplicates = 0
    skipped_impure = 0

    with open(input_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception as e:
                print(f"[-] Malformed JSON at line {line_num}: {e}")
                continue

            stmt = rec.get("statement", rec.get("theorem_statement", ""))
            stmt_hash = rec.get("stmt_hash") or compute_stmt_hash(stmt)
            axioms_count = rec.get("axioms_count", 0)

            # Axiom purity check
            if axioms_count != 0:
                skipped_impure += 1
                continue

            # Deduplication check
            if stmt_hash in existing_hashes:
                skipped_duplicates += 1
                continue

            step_id = rec.get("step_id", len(existing_hashes) + len(new_records) + 1)
            certified = rec.get("certified", True)

            entry = {
                "step_id": int(step_id),
                "stmt_hash": str(stmt_hash),
                "statement": str(stmt),
                "axioms_count": int(axioms_count),
                "certified": bool(certified)
            }
            new_records.append(entry)
            existing_hashes.add(stmt_hash)

    print(f"[*] Parsing complete:")
    print(f"    Valid unique entries to ingest: {len(new_records):,}")
    print(f"    Skipped duplicates:             {skipped_duplicates:,}")
    print(f"    Skipped impure axioms:          {skipped_impure:,}")

    if not new_records:
        print("[!] No new entries to write to Parquet lake.")
        return 0

    # Write in blocks
    next_idx = get_next_block_index(lake_dir)
    blocks_written = 0
    for chunk_start in range(0, len(new_records), block_size):
        chunk = new_records[chunk_start : chunk_start + block_size]
        table = pa.Table.from_pylist(chunk)
        block_filename = f"block_{next_idx:05d}.parquet"
        out_path = os.path.join(lake_dir, block_filename)
        pq.write_table(table, out_path, compression="zstd")
        print(f"[✓] Written partition {block_filename} with {len(chunk):,} records.")
        next_idx += 1
        blocks_written += 1

    print(f"[✓] Successfully ingested {len(new_records):,} records across {blocks_written} partition block(s).")
    return len(new_records)


def main():
    parser = argparse.ArgumentParser(description="Ingest theorem records into IMF Parquet Lake.")
    parser.add_argument("input_jsonl", help="Path to input JSONL containing theorem objects")
    parser.add_argument("--lake-dir", default="dist/parquet_lake", help="Path to destination Parquet Lake directory")
    parser.add_argument("--block-size", type=int, default=10000, help="Max records per Parquet partition")
    args = parser.parse_args()

    ingest_records(args.input_jsonl, lake_dir=args.lake_dir, block_size=args.block_size)


if __name__ == "__main__":
    main()
