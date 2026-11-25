"""
Autonomous Parquet Lake Auto-Compactor Daemon
Target: Aggregate 10 individual 1M-step Parquet partitions into 10M-step super-partitions
for high-speed DuckDB analytics and continuous distillation indexing.
"""

import os
import glob
import duckdb
import pyarrow.parquet as pq

PARQUET_LAKE_DIR = "dist/parquet_lake"
COMPACTED_DIR = "dist/parquet_lake/compacted_10m"
os.makedirs(COMPACTED_DIR, exist_ok=True)

def compact_lake():
    con = duckdb.connect()
    print("=== IMF Parquet Delta Lake Auto-Compactor ===")

    # Scan all 100 blocks
    all_files = sorted(glob.glob(os.path.join(PARQUET_LAKE_DIR, "block_*.parquet")))
    print(f"Total single-block Parquet partitions detected: {len(all_files)}")

    # Group into batches of 10 blocks (10M steps each)
    super_batches = len(all_files) // 10
    compacted_count = 0

    for b in range(super_batches):
        start_blk = b * 10 + 1
        end_blk = (b + 1) * 10
        super_name = f"super_block_{start_blk:05d}_to_{end_blk:05d}.parquet"
        out_path = os.path.join(COMPACTED_DIR, super_name)

        if os.path.exists(out_path):
            continue

        # Files in this range
        batch_files = [
            os.path.join(PARQUET_LAKE_DIR, f"block_{i:05d}.parquet")
            for i in range(start_blk, end_blk + 1)
        ]
        existing_files = [f for f in batch_files if os.path.exists(f)]

        if len(existing_files) == 10:
            query = f"""
            COPY (SELECT * FROM read_parquet({existing_files}))
            TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD);
            """
            con.execute(query)
            meta = pq.read_metadata(out_path)
            print(f"[✓] Created Super-Partition {super_name}: {meta.num_rows} rows, {meta.serialized_size / 1024 / 1024:.2f} MB")
            compacted_count += 1

    total_compacted = len(glob.glob(os.path.join(COMPACTED_DIR, "*.parquet")))
    print(f"Compaction cycle complete. Active 10M super-partitions: {total_compacted}/10")

if __name__ == "__main__":
    compact_lake()
