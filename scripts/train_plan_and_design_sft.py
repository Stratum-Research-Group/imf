"""
Targeted Fine-Tuning for Plan-Before-Code Reasoning & Modern UI Design Flare.
Aligns IMF 1.14B to:
- Resolve complex linguistic ambiguity via <plan> decomposition.
- Commit to aesthetic palettes and visual rules in <design>.
- Emit functional, modern single-page apps with procedural SVG art in <code>.
"""

import os
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
import time
import math
import torch
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.kronecker_factorized_adamw import KroneckerFactorizedAdamW
from imf.imf_model_loader import load_imf_state_dict
from imf.imf_container import IMFWriter
from imf.code_bpe_tokenizer import CodeBPETokenizer

def train():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 80)
    print("  IMF 1.14B: PLAN-AND-DESIGN ALIGNMENT FINE-TUNING")
    print(f"  Device: {torch.cuda.get_device_name(0)} | VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    print("=" * 80)

    tokenizer_path = "checkpoints/hybrid_bpe_tokenizer_4k.json"
    tok = CodeBPETokenizer.load(tokenizer_path)
    vocab_size = len(tok.vocab)

    tokens = torch.load("data/expanded_corpus/plan_and_design_tokens.pt", map_location="cpu").long()
    n_tokens = len(tokens)
    print(f"[✓] Loaded {n_tokens:,} plan-and-design tokens.")

    model = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=576,
        num_layers=16,
        num_heads=8,
        polytope_dim=8,
        num_experts=16,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.2,
    ).to(device)

    print("[*] Loading foundation weights from checkpoints/imf_foundation_1b.imf...")
    sd = load_imf_state_dict("checkpoints/imf_foundation_1b.imf", device=device)
    model.load_state_dict(sd, strict=False)
    del sd

    for layer in model.layers:
        layer.use_checkpointing = True
        layer.ssm.raw_generator.requires_grad = False
        layer.ssm.log_delta.requires_grad = False

    optimizer = KroneckerFactorizedAdamW(
        model.parameters(),
        lr=2.5e-5,
        betas=(0.0, 0.999),
        weight_decay=0.01,
    )

    batch_size = 4
    seq_len = 128
    grad_accum_steps = 2
    max_steps = 60
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_steps, eta_min=5.0e-6)

    def get_batch():
        ix = torch.randint(0, n_tokens - seq_len - 1, (batch_size,))
        x = torch.stack([tokens[i : i + seq_len] for i in ix]).to(device)
        y = torch.stack([tokens[i + 1 : i + 1 + seq_len] for i in ix]).to(device)
        return x, y

    print(f"[*] Optimizing over {max_steps} targeted alignment steps...")
    model.train()
    start_time = time.perf_counter()

    for step in range(1, max_steps + 1):
        optimizer.zero_grad()
        loss_accum = 0.0

        for _ in range(grad_accum_steps):
            x, y = get_batch()
            with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                logits, _, metrics = model(x, targets=y)
                loss = metrics["loss_pred"] / grad_accum_steps
            loss.backward()
            loss_accum += loss.item()

        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        if step % 15 == 0 or step == 1 or step == max_steps:
            ppl = math.exp(min(loss_accum, 20.0))
            elapsed = time.perf_counter() - start_time
            print(f"Step {step:2d}/{max_steps} | Loss: {loss_accum:.4f} | Perplexity: {ppl:6.2f} | Elapsed: {elapsed:.1f}s")

    print("[*] Packaging Plan-and-Design aligned weights into checkpoints/imf_foundation_1b.imf...")
    model.eval()
    cpu_state_dict = {k: v.cpu() for k, v in model.state_dict().items()}
    torch.save(cpu_state_dict, "checkpoints/imf_foundation_1b_sft.pt")

    writer = IMFWriter("checkpoints/imf_foundation_1b.imf", model_config={
        "vocab_size": vocab_size,
        "d_model": 576,
        "num_layers": 16,
        "num_heads": 8,
        "polytope_dim": 8,
        "num_experts": 16,
        "alignment": "Plan-Design-Code-Aligned",
    })
    for k, v in cpu_state_dict.items():
        writer.add_tensor(k, v)
    writer.write()
    print("[✓] Plan-and-Design SFT alignment complete! Container updated.")

if __name__ == "__main__":
    train()
