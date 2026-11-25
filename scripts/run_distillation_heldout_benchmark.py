import os
import sys
import json
import time
import math
import subprocess
import torch
import torch.nn as nn
import torch.nn.functional as F

def get_text_tokens(device, vocab_size=256):
    text_path = "data/real_text_sample.txt"
    if not os.path.exists(text_path):
        raise FileNotFoundError(f"Missing {text_path}")
    with open(text_path, "r", encoding="utf-8") as f:
        text = f.read()
    raw_bytes = list(text.encode("utf-8"))
    tokens = torch.tensor([b % vocab_size for b in raw_bytes], dtype=torch.long, device=device)
    # Split 80% train, 20% held-out
    split_idx = int(len(tokens) * 0.8)
    train_tokens = tokens[:split_idx]
    held_out_tokens = tokens[split_idx:]
    return train_tokens, held_out_tokens

def make_batches(tokens, batch_size=16, seq_len=128):
    n_batches = (len(tokens) - 1) // (batch_size * seq_len)
    total_tokens = n_batches * batch_size * seq_len
    x_flat = tokens[:total_tokens]
    y_flat = tokens[1:total_tokens + 1]
    x_batches = x_flat.view(n_batches, batch_size, seq_len)
    y_batches = y_flat.view(n_batches, batch_size, seq_len)
    return x_batches, y_batches

def build_small_lm(vocab_size=256, d_model=64, num_layers=2):
    class SmallLM(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Embedding(vocab_size, d_model)
            layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=4, dim_feedforward=d_model * 2, batch_first=True)
            self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)
            self.head = nn.Linear(d_model, vocab_size)
        def forward(self, x):
            S = x.shape[1]
            mask = nn.Transformer.generate_square_subsequent_mask(S, device=x.device)
            h = self.embed(x)
            out = self.encoder(h, mask=mask, is_causal=True)
            return self.head(out)
    return SmallLM()

def eval_model(m, held_x, held_y):
    m.eval()
    total_loss = 0.0
    with torch.no_grad():
        for b in range(len(held_x)):
            l = F.cross_entropy(m(held_x[b]).view(-1, 256), held_y[b].view(-1))
            total_loss += l.item()
    return total_loss / max(len(held_x), 1)

def run_distillation_experiment():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    git_rev = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    
    train_tok, held_tok = get_text_tokens(device=device, vocab_size=256)
    train_x, train_y = make_batches(train_tok, batch_size=16, seq_len=128)
    held_x, held_y = make_batches(held_tok, batch_size=16, seq_len=128)
    
    num_train_batches = len(train_x)
    total_steps = 200
    uniform_random_loss = math.log(256.0) # ~5.545
    
    # 1. Train Teacher model on multi-epoch text for total_steps
    torch.manual_seed(100)
    teacher = build_small_lm(vocab_size=256, d_model=96, num_layers=3).to(device)
    t_opt = torch.optim.AdamW(teacher.parameters(), lr=2e-3)
    teacher.train()
    for s in range(total_steps):
        b_idx = s % num_train_batches
        logits = teacher(train_x[b_idx])
        loss = F.cross_entropy(logits.view(-1, 256), train_y[b_idx].view(-1))
        t_opt.zero_grad()
        loss.backward()
        t_opt.step()
    teacher.eval()
    
    teacher_held_out = eval_model(teacher, held_x, held_y)
    
    # 2. Train Student CONTROL baseline: Cross-Entropy only (no teacher distillation)
    torch.manual_seed(42)
    student_ce = build_small_lm(vocab_size=256, d_model=48, num_layers=1).to(device)
    s_ce_opt = torch.optim.AdamW(student_ce.parameters(), lr=3e-3)
    
    init_held_out = eval_model(student_ce, held_x, held_y)
    
    student_ce.train()
    for s in range(total_steps):
        b_idx = s % num_train_batches
        logits = student_ce(train_x[b_idx])
        loss = F.cross_entropy(logits.view(-1, 256), train_y[b_idx].view(-1))
        s_ce_opt.zero_grad()
        loss.backward()
        s_ce_opt.step()
    final_held_out_ce_only = eval_model(student_ce, held_x, held_y)
    
    # 3. Train Student WITH Knowledge Distillation (CE + KL from Teacher)
    torch.manual_seed(42)
    student_kd = build_small_lm(vocab_size=256, d_model=48, num_layers=1).to(device)
    s_kd_opt = torch.optim.AdamW(student_kd.parameters(), lr=3e-3)
    
    t0 = time.time()
    student_kd.train()
    for s in range(total_steps):
        b_idx = s % num_train_batches
        with torch.no_grad():
            t_logits = teacher(train_x[b_idx])
        s_logits = student_kd(train_x[b_idx])
        ce = F.cross_entropy(s_logits.view(-1, 256), train_y[b_idx].view(-1))
        kl = F.kl_div(
            F.log_softmax(s_logits / 2.0, dim=-1),
            F.softmax(t_logits / 2.0, dim=-1),
            reduction='batchmean'
        ) * 4.0
        loss = 0.5 * ce + 0.5 * kl
        s_kd_opt.zero_grad()
        loss.backward()
        s_kd_opt.step()
        
    dur = time.time() - t0
    final_held_out_kd = eval_model(student_kd, held_x, held_y)
    
    # Reductions:
    # 1. Total reduction from untrained initial random baseline to final KD
    reduction_from_init = (init_held_out - final_held_out_kd) / init_held_out * 100.0
    # 2. Distillation delta vs CE-only student control baseline
    kd_delta_vs_ce = (final_held_out_ce_only - final_held_out_kd) / final_held_out_ce_only * 100.0
    
    if kd_delta_vs_ce > 1.0:
        verdict = f"Distillation provides measurable gain over CE control (+{kd_delta_vs_ce:.2f}% relative to CE baseline)"
    elif kd_delta_vs_ce > -1.0:
        verdict = f"Distillation performance comparable to CE-only control (delta {kd_delta_vs_ce:+.2f}%)"
    else:
        verdict = f"CE-only control outperformed distillation (delta {kd_delta_vs_ce:+.2f}%)"
    
    results = {
        "git_commit": git_rev,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "task": "Next-Token Knowledge Distillation on Real Text Stream (TinyShakespeare / ASCII)",
        "dataset": "real_text_sample.txt (50,000 chars)",
        "training_steps": total_steps,
        "train_batches_per_epoch": num_train_batches,
        "epochs_trained": round(total_steps / num_train_batches, 2),
        "uniform_random_loss_baseline": float(uniform_random_loss),
        "teacher_params": sum(p.numel() for p in teacher.parameters()),
        "student_params": sum(p.numel() for p in student_kd.parameters()),
        "teacher_held_out_loss": float(teacher_held_out),
        "student_initial_held_out_loss": float(init_held_out),
        "student_ce_only_control_loss": float(final_held_out_ce_only),
        "student_distilled_held_out_loss": float(final_held_out_kd),
        "held_out_loss_reduction_pct": float(reduction_from_init),
        "distillation_gain_vs_ce_control_pct": float(kd_delta_vs_ce),
        "duration_seconds": float(dur),
        "verdict": verdict
    }
    
    out_path = "benchmark_results/distill_heldout.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Distillation Real-Text Multi-Epoch Results ({total_steps} steps):")
    print(f"  Uniform Random Baseline: {uniform_random_loss:.3f}")
    print(f"  Teacher Loss: {teacher_held_out:.3f}")
    print(f"  Student Init: {init_held_out:.3f}")
    print(f"  Student CE-Only Control: {final_held_out_ce_only:.3f}")
    print(f"  Student Distilled (KD):  {final_held_out_kd:.3f}")
    print(f"  KD vs CE Control Delta:  {kd_delta_vs_ce:+.2f}%")
    print(f"  Verdict: {verdict}")
    print(f"Saved to {out_path}")

if __name__ == '__main__':
    run_distillation_experiment()
