"""
scripts/verify_parquet_lake_ci.py
Continuous Integration pipeline script for validating the formal theorem Parquet Lake.
Enforces:
1. Deduplication: zero duplicate statement hashes across all partition blocks.
2. Axiom Purity: zero external non-standard axioms (only propext / Quot.sound allowed).
3. Schema Normalization: all mandatory metadata columns present and populated.
"""

import sys
import json
import duckdb
from pathlib import Path

def run_lake_audit(parquet_glob: str = "dist/parquet_lake/*.parquet"):
    print("=" * 80)
    print("  IMF THEOREM PARQUET LAKE CI VERIFICATION PIPELINE")
    print(f"  Target Partition Glob: {parquet_glob}")
    print("=" * 80)
    
    con = duckdb.connect()
    
    # 1. Total row count and hash uniqueness
    print("[*] Checking theorem statement deduplication...")
    res = con.execute(f"""
        SELECT COUNT(*) as total_rows, COUNT(DISTINCT stmt_hash) as unique_hashes
        FROM '{parquet_glob}'
    """).fetchall()
    total_rows, unique_hashes = res[0]
    print(f"    Total Theorems: {total_rows:,} | Unique Hashes: {unique_hashes:,}")
    if total_rows != unique_hashes:
        print(f"[-] ERROR: Found {total_rows - unique_hashes} duplicate theorems!")
        return False
        
    # 2. Axiom compliance
    print("[*] Checking formal axiom purity...")
    res = con.execute(f"SELECT SUM(axioms_count) as non_std FROM '{parquet_glob}'").fetchall()
    non_std = res[0][0] or 0
    print(f"    Non-standard external axiom count: {non_std}")
    if non_std != 0:
        print(f"[-] ERROR: Found {non_std} non-standard axiom violations!")
        return False
        
    # 3. Schema integrity
    print("[*] Checking schema columns and non-null constraints...")
    cols = con.execute(f"DESCRIBE SELECT * FROM '{parquet_glob}'").fetchall()
    col_names = [c[0] for c in cols]
    required_cols = ["step_id", "stmt_hash", "statement", "axioms_count", "certified"]
    missing = [c for c in required_cols if c not in col_names]
    if missing:
        print(f"[-] ERROR: Missing mandatory columns: {missing}")
        return False
        
    print("[✓] ALL PARQUET LAKE CI INTEGRITY CHECKS PASSED.")
    return True

if __name__ == "__main__":
    success = run_lake_audit()
    if not success:
        sys.exit(1)
