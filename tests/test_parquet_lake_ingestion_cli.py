"""
tests/test_parquet_lake_ingestion_cli.py
Tests the automated theorem lake ingestion CLI and deduplication/purity filtering.
"""

import os
import json
import tempfile
import duckdb
from scripts.ingest_theorems_to_lake import ingest_records


def test_parquet_lake_ingest():
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "sample_theorems.jsonl")
        sample_records = [
            {"statement": "theorem thm_1 : 1 + 1 = 2 := by rfl", "axioms_count": 0, "certified": True},
            {"statement": "theorem thm_2 : True := by trivial", "axioms_count": 0, "certified": True},
            # Impure entry (axioms_count > 0)
            {"statement": "theorem thm_impure : False := by sorry", "axioms_count": 1, "certified": False},
            # Duplicate entry
            {"statement": "theorem thm_1 : 1 + 1 = 2 := by rfl", "axioms_count": 0, "certified": True},
        ]
        with open(input_file, "w", encoding="utf-8") as f:
            for r in sample_records:
                f.write(json.dumps(r) + "\n")

        lake_dir = os.path.join(tmpdir, "lake")
        ingested = ingest_records(input_file, lake_dir=lake_dir, block_size=10)
        assert ingested == 2

        con = duckdb.connect()
        rows = con.execute(f"SELECT COUNT(*) FROM '{lake_dir}/block_*.parquet'").fetchall()[0][0]
        assert rows == 2
