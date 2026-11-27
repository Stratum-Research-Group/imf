#!/usr/bin/env python3
"""
benchmark_parquet_lake_zero_copy_mmap.py
Zero-copy memory-mapped high-throughput Parquet scanner for IMF corpus manifest blocks.
Demonstrates low-latency chunk decompression and columnar scanning across sealed blocks.
"""

import os
import sys
import time
import pyarrow as pa
import pyarrow.parquet as pq

def run_benchmark():
    lake_dir = "dist/parquet_lake"
    if not os.path.exists(lake_dir):
        print(f"[!] Parquet lake directory {lake_dir} not found.")
        return 1

    files = [os.path.join(lake_dir, f) for f in os.listdir(lake_dir) if f.endswith(".parquet")]
    if not files:
        print("[!] No parquet files found in lake.")
        return 1

    print(f"[*] Benchmark: Zero-Copy Parquet Lake Columnar Scanner")
    print(f"[*] Found {len(files)} partition chunk(s) in {lake_dir}:")
    for f in sorted(files):
        sz_kb = os.path.getsize(f) / 1024.0
        print(f"    • {os.path.basename(f)} ({sz_kb:.1f} KB)")

    total_rows = 0
    total_bytes = 0

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        curr_rows = 0
        for fpath in files:
            # Memory-mapped zero-copy read
            source = pa.memory_map(fpath, 'r')
            parquet_file = pq.ParquetFile(source)
            table = parquet_file.read(columns=['block_id', 'step_count'])
            curr_rows += table.num_rows
            total_bytes += source.size()
        total_rows = curr_rows

    t1 = time.perf_counter()
    elapsed = (t1 - t0) / iters
    scan_throughput_mb = (total_bytes / iters) / (elapsed * 1024 * 1024)
    rows_per_sec = total_rows / elapsed

    print(f"\n[✓] Scanned {total_rows:,} sealed block records in {elapsed*1000:.3f} ms")
    print(f"[✓] Zero-copy memory-mapped throughput: {scan_throughput_mb:.2f} MB/s")
    print(f"[✓] Record scanning rate: {rows_per_sec:,.0f} rows/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
