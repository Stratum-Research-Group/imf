"""
imf/mmap_parquet_streamer.py
Zero-Copy Memory-Mapped Parquet Streamer for Real-Time SFT / Distillation.
Streams tokenized theorems directly from partitioned Parquet lake files
using pyarrow memory mapping into PyTorch Datasets with minimal host RAM footprint.
Author: Nicholas Charles Mynhardt (Stratum Research Group)
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator
import pyarrow.parquet as pq
import pyarrow as pa
import torch
from torch.utils.data import IterableDataset


class MmapParquetTheoremDataset(IterableDataset):
    """
    Zero-copy memory-mapped theorem dataset.
    Reads directly from memory-mapped Parquet row-groups.
    """
    def __init__(
        self,
        parquet_paths: List[Path],
        batch_size: int = 128,
        max_seq_len: int = 256,
        shuffle_files: bool = False
    ):
        super().__init__()
        self.parquet_paths = [Path(p) for p in parquet_paths if Path(p).exists()]
        self.batch_size = batch_size
        self.max_seq_len = max_seq_len
        self.shuffle_files = shuffle_files

    def _simple_tokenize(self, text: str) -> List[int]:
        """Byte-level fallback tokenization for zero-overhead streaming."""
        encoded = text.encode("utf-8")
        tokens = list(encoded[:self.max_seq_len])
        if len(tokens) < self.max_seq_len:
            tokens.extend([0] * (self.max_seq_len - len(tokens)))
        return tokens

    def __iter__(self) -> Iterator[Dict[str, torch.Tensor]]:
        worker_info = torch.utils.data.get_worker_info()
        paths = list(self.parquet_paths)

        if worker_info is not None:
            # Shard across data loader workers
            paths = [p for i, p in enumerate(paths) if i % worker_info.num_workers == worker_info.id]

        for p in paths:
            # Memory map the parquet file
            mmap_source = pa.memory_map(str(p), mode="r")
            parquet_file = pq.ParquetFile(mmap_source)

            for rg_idx in range(parquet_file.num_row_groups):
                table = parquet_file.read_row_group(
                    rg_idx,
                    columns=["statement", "code"] if "code" in parquet_file.schema.names else ["statement"]
                )
                stmts = table.column("statement").to_pylist()
                codes = table.column("code").to_pylist() if "code" in table.column_names else [""] * len(stmts)

                batch_tokens = []
                batch_masks = []

                for stmt, code in zip(stmts, codes):
                    combined = f"{stmt}\n{code}".strip()
                    tokens = self._simple_tokenize(combined)
                    mask = [1 if t != 0 else 0 for t in tokens]
                    batch_tokens.append(tokens)
                    batch_masks.append(mask)

                    if len(batch_tokens) == self.batch_size:
                        yield {
                            "input_ids": torch.tensor(batch_tokens, dtype=torch.long),
                            "attention_mask": torch.tensor(batch_masks, dtype=torch.float32)
                        }
                        batch_tokens = []
                        batch_masks = []

                if batch_tokens:
                    yield {
                        "input_ids": torch.tensor(batch_tokens, dtype=torch.long),
                        "attention_mask": torch.tensor(batch_masks, dtype=torch.float32)
                    }

            mmap_source.close()


def benchmark_parquet_mmap_streamer(lake_dir: Path, batches_to_read: int = 50) -> Dict[str, float]:
    """Measures memory mapping throughput and latency."""
    import time

    parquet_files = sorted(lake_dir.glob("*.parquet"))
    if not parquet_files:
        return {"error": "No parquet files found"}

    dataset = MmapParquetTheoremDataset(parquet_paths=parquet_files, batch_size=64)
    loader = torch.utils.data.DataLoader(dataset, batch_size=None, num_workers=0)

    t0 = time.perf_counter()
    count = 0
    total_tokens = 0

    for batch in loader:
        count += 1
        total_tokens += batch["input_ids"].numel()
        if count >= batches_to_read:
            break

    elapsed = time.perf_counter() - t0
    return {
        "batches_read": count,
        "total_tokens": total_tokens,
        "elapsed_seconds": round(elapsed, 4),
        "tokens_per_second": round(total_tokens / elapsed, 2) if elapsed > 0 else 0.0,
        "latency_per_batch_ms": round((elapsed / count) * 1000.0, 3) if count > 0 else 0.0
    }


if __name__ == "__main__":
    lake = Path("dist/parquet_lake")
    res = benchmark_parquet_mmap_streamer(lake, batches_to_read=20)
    print("Mmap Parquet Streamer Benchmark:", res)
