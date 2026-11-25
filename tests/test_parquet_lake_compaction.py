"""
tests/test_parquet_lake_compaction.py
Tests the Parquet Lake compaction and point lookup indexing.
"""

import os
import tempfile
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from scripts.compact_and_index_lake import compact_parquet_lake


def test_parquet_lake_compaction_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 2 mock partition blocks
        data1 = [
            {"step_id": 1, "stmt_hash": "hash_a", "statement": "thm a", "axioms_count": 0, "certified": True},
            {"step_id": 2, "stmt_hash": "hash_b", "statement": "thm b", "axioms_count": 0, "certified": True},
        ]
        data2 = [
            {"step_id": 3, "stmt_hash": "hash_b", "statement": "thm b duplicate", "axioms_count": 0, "certified": True}, # duplicate
            {"step_id": 4, "stmt_hash": "hash_c", "statement": "thm c", "axioms_count": 1, "certified": False}, # impure
            {"step_id": 5, "stmt_hash": "hash_d", "statement": "thm d", "axioms_count": 0, "certified": True},
        ]
        pq.write_table(pa.Table.from_pylist(data1), os.path.join(tmpdir, "block_00001.parquet"))
        pq.write_table(pa.Table.from_pylist(data2), os.path.join(tmpdir, "block_00002.parquet"))

        out_compacted = os.path.join(tmpdir, "compacted.parquet")
        success = compact_parquet_lake(lake_dir=tmpdir, output_compacted=out_compacted)
        assert success is True

        con = duckdb.connect()
        rows = con.execute(f"SELECT COUNT(*) FROM '{out_compacted}'").fetchone()[0]
        # Should contain hash_a, hash_b, hash_d (3 records, omitting duplicate hash_b and impure hash_c)
        assert rows == 3
