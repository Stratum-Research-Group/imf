"""
imf/run_multi_epoch_distillation_scheduler.py
Multi-Epoch Autonomous Distillation Scheduler.
Streams through consecutive sealed blocks (e.g. Blocks 41-45),
performing continuous student model training with learning rate decay and perplexity tracking.
"""

import time
import torch
from pathlib import Path
from imf.omnilm_mope import IMFOmniLMMoPE
from imf.streaming_corpus_dataset import StreamingGrandCorpusDataset

def run_multi_epoch_scheduler(num_epochs: int = 3, max_blocks: int = 3):
    print("=" * 80)
    print("  IMF MULTI-EPOCH AUTONOMOUS DISTILLATION SCHEDULER")
    print(f"  Curriculum: Streaming {max_blocks} Sealed Blocks over {num_epochs} Epochs")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    student = IMFOmniLMMoPE(
        vocab_size=4096, d_model=256, num_layers=4, num_heads=4, num_experts=8, top_k=2, max_seq_len=64
    ).to(device)

    base_lr = 2e-4
    optimizer = torch.optim.AdamW(student.parameters(), lr=base_lr, weight_decay=0.01)
    criterion = torch.nn.CrossEntropyLoss()

    dataset = StreamingGrandCorpusDataset(corpus_dir="dist/gym_32b_corpus", max_blocks=max_blocks, seq_len=64)

    t0 = time.perf_counter()
    epoch_losses = []

    for epoch in range(1, num_epochs + 1):
        # Cosine learning rate decay
        current_lr = base_lr * (0.5 * (1.0 + torch.cos(torch.tensor(epoch / num_epochs * 3.14159)).item()))
        for param_group in optimizer.param_groups:
            param_group["lr"] = current_lr

        batch_buf = []
        losses = []
        step = 0

        for tensor in dataset:
            batch_buf.append(tensor)
            if len(batch_buf) == 8:
                inputs = torch.stack(batch_buf).to(device)
                targets = inputs.clone()
                batch_buf = []

                optimizer.zero_grad()
                logits, recon_loss, _ = student(inputs)
                loss = criterion(logits.reshape(-1, 4096), targets.reshape(-1)) + 0.1 * recon_loss.mean()
                loss.backward()
                optimizer.step()

                losses.append(loss.item())
                step += 1
                if step >= 5:  # 5 micro-batches per epoch for test demonstration
                    break

        avg_loss = sum(losses) / len(losses)
        ppl = torch.exp(torch.tensor(avg_loss)).item()
        epoch_losses.append(avg_loss)
        print(f"  [Epoch {epoch:02d}/{num_epochs:02d}] LR: {current_lr:.2e} | Mean Loss: {avg_loss:.4f} | Perplexity: {ppl:6.2f}")

    elapsed = time.perf_counter() - t0
    rel_red = ((epoch_losses[0] - epoch_losses[-1]) / epoch_losses[0]) * 100.0 if epoch_losses[0] > 0 else 0

    print("=" * 80)
    print(f"[✓] Multi-Epoch Curriculum Scheduler Completed in {elapsed:.2f}s")
    print(f"    Initial Loss: {epoch_losses[0]:.4f} -> Final Loss: {epoch_losses[-1]:.4f} ({rel_red:.2f}% reduction)")
    print("=" * 80)

if __name__ == "__main__":
    run_multi_epoch_scheduler(num_epochs=3, max_blocks=2)
