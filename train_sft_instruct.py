"""
Instruction Tuning (SFT) Engine for IMF-129.8M using Stanford Alpaca & Code Pairs.
Masks prompt tokens so cross-entropy loss is computed strictly on response tokens.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import time
import math
import json
import torch
import torch.nn.functional as F
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM


def build_sft_dataset(
    json_path: str = "data/expanded_corpus/alpaca_instructions_2k.json",
    tokenizer_path: str = "checkpoints/hybrid_bpe_tokenizer_4k.json",
    max_seq_len: int = 128,
):
    tok = CodeBPETokenizer.load(tokenizer_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = []
    for item in data:
        inst = item.get("instruction", "").strip()
        inp = item.get("input", "").strip()
        resp = item.get("output", "").strip()

        if inp:
            prompt = f"### Instruction:\n{inst}\n### Input:\n{inp}\n### Response:\n"
        else:
            prompt = f"### Instruction:\n{inst}\n### Response:\n"

        prompt_ids = tok.encode(prompt)
        resp_ids = tok.encode(resp + "\n")
        full_ids = prompt_ids + resp_ids

        if len(full_ids) < 10:
            continue

        # Truncate to max_seq_len
        full_ids = full_ids[:max_seq_len]
        p_len = min(len(prompt_ids), len(full_ids) - 1)

        # Mask labels: -100 for prompt tokens
        labels = [-100] * p_len + full_ids[p_len:]

        # Pad to max_seq_len
        pad_len = max_seq_len - len(full_ids)
        if pad_len > 0:
            full_ids = full_ids + [0] * pad_len
            labels = labels + [-100] * pad_len

        samples.append({
            "input_ids": full_ids,
            "labels": labels,
        })

    print(f"[✓] Formatted {len(samples)} instruction-tuning pairs.")
    return tok, samples


def run_sft_training(
    init_checkpoint: str = "checkpoints/imf_fluency_lm_4k.pt",
    output_checkpoint: str = "checkpoints/imf_sft_instruct_4k.pt",
    max_steps: int = 600,
    batch_size: int = 16,
    lr: float = 5e-5,
):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 76)
    print("IMF Instruction Tuning (SFT) Engine")
    print("=" * 76)

    tok, samples = build_sft_dataset()
    vocab_size = len(tok.vocab)

    inputs_tensor = torch.tensor([s["input_ids"] for s in samples], dtype=torch.long)
    labels_tensor = torch.tensor([s["labels"] for s in samples], dtype=torch.long)

    model = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=384,
        num_layers=4,
        num_heads=6,
        polytope_dim=8,
        num_experts=16,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.1,
    ).to(device)

    print(f"[*] Loading pretrained fluency weights from {init_checkpoint}...")
    model.load_state_dict(torch.load(init_checkpoint, map_location=device))

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95), weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_steps, eta_min=lr * 0.1)

    n_samples = len(inputs_tensor)
    split = int(0.9 * n_samples)
    train_in, train_lbl = inputs_tensor[:split], labels_tensor[:split]
    val_in, val_lbl = inputs_tensor[split:], labels_tensor[split:]

    def get_batch(inputs, labels):
        ix = torch.randint(0, len(inputs), (batch_size,))
        x = inputs[ix].to(device)
        y = labels[ix].to(device)
        return x, y

    print("\nStarting SFT Fine-Tuning...")
    model.train()
    t0 = time.perf_counter()

    for step in range(1, max_steps + 1):
        x, y = get_batch(train_in, train_lbl)
        optimizer.zero_grad(set_to_none=True)

        logits, _, metrics = model(x)
        # Shift logits and labels for autoregressive next-token loss
        shift_logits = logits[:, :-1, :].contiguous()
        shift_labels = y[:, 1:].contiguous()

        loss = F.cross_entropy(
            shift_logits.view(-1, vocab_size),
            shift_labels.view(-1),
            ignore_index=-100,
        )

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        if step % 100 == 0 or step == 1:
            model.eval()
            with torch.no_grad():
                vx, vy = get_batch(val_in, val_lbl)
                v_logits, _, _ = model(vx)
                v_shift_logits = v_logits[:, :-1, :].contiguous()
                v_shift_labels = vy[:, 1:].contiguous()
                v_loss = F.cross_entropy(
                    v_shift_logits.view(-1, vocab_size),
                    v_shift_labels.view(-1),
                    ignore_index=-100,
                ).item()

            dt = time.perf_counter() - t0
            tok_s = (step * batch_size * 128) / max(dt, 1e-6)
            print(
                f"[SFT Step {step:3d}/{max_steps:3d}] "
                f"Train Loss: {loss.item():.4f} | "
                f"Val Loss: {v_loss:.4f} | "
                f"Val PPL: {math.exp(min(v_loss, 20.0)):5.2f} | "
                f"Throughput: {tok_s:,.0f} tok/s"
            )
            model.train()

    torch.save(model.state_dict(), output_checkpoint)
    print(f"\n[✓] SFT Training complete! Saved to {output_checkpoint}")

    # Interactive instruction test
    print("\n" + "=" * 76)
    print("SFT Zero-Shot Qualitative Evaluation:")
    print("=" * 76)
    test_prompts = [
        "### Instruction:\nExplain what a Python function is.\n### Response:\n",
        "### Instruction:\nWrite a greeting to the user.\n### Response:\n",
    ]
    model.eval()
    for prompt in test_prompts:
        p_ids = tok.encode(prompt)
        curr = torch.tensor([p_ids], dtype=torch.long, device=device)
        with torch.no_grad():
            for _ in range(35):
                out_logits, _, _ = model(curr)
                nxt = out_logits[:, -1, :].argmax(dim=-1, keepdim=True)
                curr = torch.cat([curr, nxt], dim=1)
        gen = tok.decode(curr[0].tolist())
        print(f"\n{gen}")


if __name__ == "__main__":
    run_sft_training()
