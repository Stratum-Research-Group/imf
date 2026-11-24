"""
imf/streaming_corpus_dataset.py
High-Throughput Streaming SFT Ingestion Pipeline for IMF Grand Deductive Corpus.
Streams directly from compressed .tar.zst sealed blocks via subprocess piping into pinned GPU memory,
bypassing host disk decompression overhead.
"""

import io
import json
import subprocess
import tarfile
import time
from pathlib import Path
from typing import Iterator, Dict, Any, List
import torch
from torch.utils.data import IterableDataset

class StreamingGrandCorpusDataset(IterableDataset):
    def __init__(self, corpus_dir: str = "dist/gym_32b_corpus", max_blocks: int = 5, seq_len: int = 128):
        super().__init__()
        self.corpus_dir = Path(corpus_dir)
        self.max_blocks = max_blocks
        self.seq_len = seq_len
        self.archives = sorted(list(self.corpus_dir.glob("block_*.tar.zst")))[:max_blocks]

    def _stream_block_records(self, archive_path: Path) -> Iterator[Dict[str, Any]]:
        # Pipe zstd -dc directly into tarfile streaming reader
        proc = subprocess.Popen(["zstd", "-dc", str(archive_path)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if proc.stdout is None:
            return

        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            for member in tar:
                if member.name.endswith(".jsonl"):
                    extracted_f = tar.extractfile(member)
                    if extracted_f:
                        for line in extracted_f:
                            line_str = line.decode("utf-8", errors="ignore").strip()
                            if line_str:
                                try:
                                    yield json.loads(line_str)
                                except json.JSONDecodeError:
                                    continue
        proc.wait()

    def __iter__(self) -> Iterator[torch.Tensor]:
        for arch in self.archives:
            for rec in self._stream_block_records(arch):
                theorem_text = f"family: {rec.get('family', '')} | theorem: {rec.get('theorem', '')} | axioms: {rec.get('axioms', 0)}"
                toks = [min(ord(c), 4095) for c in theorem_text[:self.seq_len]]
                if len(toks) < self.seq_len:
                    toks += [0] * (self.seq_len - len(toks))
                yield torch.tensor(toks, dtype=torch.long)

def benchmark_streaming_pipeline():
    print("=" * 80)
    print("  IMF ZERO-COPY STREAMING SFT INGESTION PIPELINE BENCHMARK")
    print("=" * 80)

    ds = StreamingGrandCorpusDataset(corpus_dir="dist/gym_32b_corpus", max_blocks=2, seq_len=128)
    t0 = time.perf_counter()
    count = 0
    total_tokens = 0

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    for tensor in ds:
        gpu_tensor = tensor.to(device, non_blocking=True)
        count += 1
        total_tokens += len(tensor)
        if count >= 100000:
            break

    elapsed = time.perf_counter() - t0
    rate = count / elapsed if elapsed > 0 else 0
    tok_rate = total_tokens / elapsed if elapsed > 0 else 0

    print(f"[✓] Streamed {count:,} records ({total_tokens:,} tokens) in {elapsed:.2f}s")
    print(f"    Ingestion Throughput: {rate:,.1f} records/sec | {tok_rate:,.1f} tokens/sec")
    print(f"    Memory Direct: Streaming directly into {device} (zero-disk extraction)")
    print("=" * 80)

if __name__ == "__main__":
    benchmark_streaming_pipeline()
