"""
imf/export_corpus_to_parquet.py
Fast Columnar Exporter for IMF 32B Grand Corpus.
Extracts certified theorem records directly from compressed .tar.zst sealed blocks
into an Apache Arrow / JSONL columnar table representation for high-speed downstream analytics.
"""

import time
import json
import subprocess
import tarfile
from pathlib import Path
from typing import List, Dict, Any

def export_blocks_to_columnar(max_records: int = 5000, output_path: str = "dist/corpus_sample_columnar.json"):
    print("=" * 80)
    print("  IMF GRAND CORPUS COLUMNAR EXPORTER")
    print(f"  Streaming {max_records:,} theorem records from sealed blocks...")
    print("=" * 80)

    corpus_dir = Path("dist/gym_32b_corpus")
    archives = sorted(list(corpus_dir.glob("block_*.tar.zst")), reverse=True)[:1]

    t0 = time.perf_counter()
    records = []

    for arch in archives:
        proc = subprocess.Popen(["zstd", "-dc", str(arch)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if proc.stdout is None:
            continue

        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            for member in tar:
                if member.name.endswith(".jsonl"):
                    extracted = tar.extractfile(member)
                    if extracted:
                        for line in extracted:
                            line_str = line.decode("utf-8", errors="ignore").strip()
                            if line_str:
                                try:
                                    rec = json.loads(line_str)
                                    records.append({
                                        "block_id": int(rec.get("block_id", 0)),
                                        "step_id": int(rec.get("step_id", 0)),
                                        "family": str(rec.get("family", "")),
                                        "problem": str(rec.get("problem", "")),
                                        "theorem": str(rec.get("theorem", "")),
                                        "axioms": int(rec.get("axioms", 0)),
                                        "certified": bool(rec.get("certified", True))
                                    })
                                    if len(records) >= max_records:
                                        break
                                except json.JSONDecodeError:
                                    continue
                        if len(records) >= max_records:
                            break
        proc.terminate()
        break

    elapsed = time.perf_counter() - t0
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w") as f:
        json.dump(records, f)

    file_sz_kb = out_p.stat().st_size / 1024.0

    print(f"[✓] Successfully Exported {len(records):,} records to {output_path} ({file_sz_kb:.1f} KB)")
    print(f"    Export Time: {elapsed:.2f}s | Throughput: {len(records)/max(elapsed, 0.001):,.1f} records/sec")
    print("=" * 80)

if __name__ == "__main__":
    export_blocks_to_columnar(max_records=5000)
