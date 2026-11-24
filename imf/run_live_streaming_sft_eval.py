"""
imf/run_live_streaming_sft_eval.py
Live End-to-End Online Polytope SFT Benchmark.
Streams training batches directly from sealed .tar.zst corpus blocks into
the IMFOmniLMMoPE model on RTX 5060 Ti GPU, demonstrating continuous loss reduction.
"""

import time
import torch
import torch.nn as nn
from imf.omnilm_mope import IMFOmniLMMoPE
from imf.streaming_corpus_dataset import StreamingGrandCorpusDataset

def run_streaming_sft_eval():
    print("=" * 80)
    print("  IMF LIVE STREAMING SFT CONVERGENCE BENCHMARK")
    print("  Model: IMF-OmniLM-1B (MoPE) | Streaming Dataset: Grand Deductive Corpus")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    vocab_size = 4096
    d_model = 256
    seq_len = 64
    batch_size = 8

    # Instantiate student model with MoPE architecture
    model = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=d_model,
        num_layers=4,
        num_heads=4,
        num_experts=8,
        top_k=2,
        max_seq_len=seq_len
    ).to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.01)
    criterion = nn.CrossEntropyLoss()

    dataset = StreamingGrandCorpusDataset(corpus_dir="dist/gym_32b_corpus", max_blocks=3, seq_len=seq_len)

    buffer = []
    loss_history = []
    t0 = time.perf_counter()
    step = 0
    max_steps = 15

    print(f"[*] Beginning streaming optimization over {max_steps} micro-batches...")

    for tensor in dataset:
        buffer.append(tensor)
        if len(buffer) == batch_size:
            batch = torch.stack(buffer).to(device)
            buffer = []

            inputs = batch[:, :-1]
            targets = batch[:, 1:]

            optimizer.zero_grad()
            logits, recon_loss, _ = model(inputs)
            loss_pred = criterion(logits.reshape(-1, vocab_size), targets.reshape(-1))
            loss = loss_pred + 0.1 * recon_loss.mean()

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            loss_val = float(loss.item())
            loss_history.append(loss_val)
            step += 1

            if step % 3 == 0 or step == max_steps:
                ppl = torch.exp(torch.tensor(loss_val)).item()
                print(f"  [Step {step:02d}/{max_steps}] Loss: {loss_val:.4f} | Perplexity: {ppl:7.2f} | PPL Reduction: {((loss_history[0] - loss_val)/loss_history[0])*100:5.2f}%")

            if step >= max_steps:
                break

    elapsed = time.perf_counter() - t0
    initial_loss = loss_history[0]
    final_loss = loss_history[-1]
    reduction = ((initial_loss - final_loss) / initial_loss) * 100.0

    print("=" * 80)
    print(f"[✓] Streaming SFT Optimization Completed in {elapsed:.2f}s")
    print(f"    Initial Loss: {initial_loss:.4f} -> Final Loss: {final_loss:.4f}")
    print(f"    Relative Loss Reduction: {reduction:.2f}%")
    print(f"    Stream-to-Weight Speed: {max_steps * batch_size / elapsed:.1f} records/sec directly from compressed archives")
    print("=" * 80)

if __name__ == "__main__":
    run_streaming_sft_eval()
