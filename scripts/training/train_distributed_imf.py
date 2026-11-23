"""
train_distributed_imf.py
Distributed Data Parallel (DDP) / Multi-GPU Training Harness for IMF-OmniLM.
Enables high-throughput multi-GPU pretraining across nodes.

Usage:
    torchrun --nproc_per_node=2 train_distributed_imf.py --steps 1000 --batch-size 32
"""

import os
import argparse
import time
import math
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import DataLoader, Dataset, DistributedSampler

from imf.bpe_tokenizer import BPETokenizer
from train_omni_lm import IMFOmniLM


class TokenDataset(Dataset):
    def __init__(self, data: torch.Tensor, seq_len: int):
        self.data = data
        self.seq_len = seq_len

    def __len__(self):
        return len(self.data) - self.seq_len - 1

    def __getitem__(self, idx):
        x = self.data[idx : idx + self.seq_len]
        y = self.data[idx + 1 : idx + self.seq_len + 1]
        return x, y


def setup_ddp():
    if "RANK" in os.environ and "WORLD_SIZE" in os.environ:
        rank = int(os.environ["RANK"])
        world_size = int(os.environ["WORLD_SIZE"])
        local_rank = int(os.environ["LOCAL_RANK"])
        torch.cuda.set_device(local_rank)
        dist.init_process_group("nccl", rank=rank, world_size=world_size)
        return rank, world_size, local_rank
    else:
        # Fallback to single-process CPU/CUDA simulation
        return 0, 1, 0


def cleanup_ddp():
    if dist.is_initialized():
        dist.destroy_process_group()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seq-len", type=int, default=64)
    parser.add_argument("--d-model", type=int, default=128)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--n-layers", type=int, default=2)
    parser.add_argument("--lr", type=float, default=6e-4)
    args = parser.parse_args()

    rank, world_size, local_rank = setup_ddp()
    device = torch.device(f"cuda:{local_rank}" if torch.cuda.is_available() else "cpu")

    if rank == 0:
        print("="*75)
        print(f"Distributed Data Parallel (DDP) Multi-GPU Training Harness for IMF-OmniLM")
        print(f"World Size: {world_size} GPUs | Process Local Rank: {local_rank} on {device}")
        print("="*75)

    vocab_path = Path("data/tinystories_bpe.json")
    tokenizer = BPETokenizer.load(vocab_path)
    vocab_size = tokenizer.vocab_size

    # Load corpus
    data_path = Path("data/tinystories_sample.pt")
    corpus = torch.load(data_path, weights_only=True)
    if isinstance(corpus, dict) and "tokens" in corpus:
        corpus = corpus["tokens"]

    train_data = corpus[:-50000]
    val_data = corpus[-50000:]

    dataset = TokenDataset(train_data, args.seq_len)
    sampler = DistributedSampler(dataset, num_replicas=world_size, rank=rank, shuffle=True) if world_size > 1 else None
    loader = DataLoader(dataset, batch_size=args.batch_size, sampler=sampler, shuffle=(sampler is None))

    # Instantiate model
    model = IMFOmniLM(
        vocab_size=vocab_size,
        d_model=args.d_model,
        num_heads=args.num_heads,
        n_layers=args.n_layers,
        polytope_dim=10,
        conv_rank=32,
        conv_window=6,
        use_triton_ssm=False,
    ).to(device)

    if world_size > 1:
        model = DDP(model, device_ids=[local_rank] if torch.cuda.is_available() else None)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-2)
    criterion = nn.CrossEntropyLoss()

    model.train()
    step = 0
    t0 = time.time()

    for epoch in range(10):
        if sampler is not None:
            sampler.set_epoch(epoch)

        for bx, by in loader:
            step += 1
            bx, by = bx.to(device, non_blocking=True), by.to(device, non_blocking=True)

            optimizer.zero_grad()
            logits = model(bx)
            loss = criterion(logits.view(-1, vocab_size), by.view(-1))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            if rank == 0 and (step % 100 == 0 or step == args.steps):
                ppl = math.exp(min(loss.item(), 20.0))
                print(f"  Step {step:4d}/{args.steps} | Loss: {loss.item():.4f} | Perplexity: {ppl:.2f}")

            if step >= args.steps:
                break
        if step >= args.steps:
            break

    if rank == 0:
        elapsed = time.time() - t0
        print(f"[✓] Distributed Training completed in {elapsed:.2f}s ({elapsed / args.steps * 1000.0:.2f} ms/step)")
        out_path = Path("checkpoints/imf_omni_lm_ddp.pt")
        raw_model = model.module if hasattr(model, "module") else model
        torch.save({
            "step": args.steps,
            "model_state_dict": raw_model.state_dict(),
            "d_model": args.d_model,
            "num_heads": args.num_heads,
            "n_layers": args.n_layers,
            "vocab_size": vocab_size,
        }, out_path)
        print(f"[✓] Saved DDP checkpoint to {out_path}")

    cleanup_ddp()


if __name__ == "__main__":
    main()
