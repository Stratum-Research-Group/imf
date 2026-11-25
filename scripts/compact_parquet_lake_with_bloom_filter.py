"""Bloom-filter-assisted exact dedup of the Parquet theorem lake.
The Bloom filter only flags *possible* duplicates; each flagged statement is confirmed
against an exact set, so no distinct theorem is ever dropped (Bloom false positives cost
a set lookup, not data loss). Output goes to dist/parquet_lake/compacted_bloom/.
"""
import hashlib, json, time, sys
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


class BloomFilter:
    def __init__(self, n_items: int, fp_rate: float = 0.01):
        self.m = max(64, int(-n_items * np.log(fp_rate) / (np.log(2) ** 2)))
        self.k = max(1, int(round(self.m / max(n_items, 1) * np.log(2))))
        self.bits = np.zeros((self.m + 7) // 8, dtype=np.uint8)

    def _idx(self, s: str):
        d = hashlib.blake2b(s.encode(), digest_size=16).digest()
        h1, h2 = int.from_bytes(d[:8], "little"), int.from_bytes(d[8:], "little") | 1
        return [(h1 + i * h2) % self.m for i in range(self.k)]

    def add_check(self, s: str) -> bool:
        """Adds s; returns True if it was possibly already present."""
        present = True
        for i in self._idx(s):
            byte, bit = i >> 3, 1 << (i & 7)
            if not self.bits[byte] & bit:
                present = False
                self.bits[byte] |= bit
        return present


def main(lake=Path("dist/parquet_lake"), out_dir=None):
    out_dir = Path(out_dir or lake / "compacted_bloom")
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(lake.glob("*.parquet"))
    n_total = sum(pq.ParquetFile(f).metadata.num_rows for f in files)
    bf, seen = BloomFilter(n_total), set()
    kept, flagged, dropped, in_bytes = [], 0, 0, 0
    t0 = time.perf_counter()
    for f in files:
        in_bytes += f.stat().st_size
        t = pq.read_table(f)
        keep = []
        for i, st in enumerate(t.column("statement").to_pylist()):
            if bf.add_check(st):
                flagged += 1
                if st in seen:
                    dropped += 1
                    continue
            seen.add(st)
            keep.append(i)
        kept.append(t.take(keep))
    out = pa.concat_tables(kept)
    pq.write_table(out, out_dir / "compacted_theorems.parquet", compression="zstd")
    dt = time.perf_counter() - t0
    stmts = out.column("statement").to_pylist()
    rep = {"input_rows": n_total, "output_rows": out.num_rows, "bloom_flagged": flagged,
           "exact_duplicates_dropped": dropped, "bloom_false_positives_rescued": flagged - dropped,
           "output_distinct": len(set(stmts)), "bloom_bits": bf.m, "bloom_k": bf.k,
           "elapsed_s": round(dt, 3), "throughput_MBps": round(in_bytes / 1e6 / dt, 2)}
    assert rep["output_distinct"] == rep["output_rows"]
    Path("benchmark_results/bloom_compaction.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    return rep


if __name__ == "__main__":
    main()
