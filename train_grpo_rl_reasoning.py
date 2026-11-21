"""
Phase 2: Verifiable GRPO (Group Relative Policy Optimization) on IMF-107.7M Flagship.
Optimizes the flagship model using verifiable execution feedback on code and arithmetic reasoning.
Group Relative Advantage: A_i = (R_i - mean(R)) / (std(R) + 1e-8)
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import sys
import ast
import time
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

torch.set_num_threads(1)
torch.set_num_interop_threads(1)

from imf.code_bpe_tokenizer import CodeBPETokenizer
from train_flagship_omnilm_mope import IMFOmniLMMoPE


# Verifiable Reasoning Tasks
PROMPT_TASKS = [
    {
        "prompt": "def add(a, b):\n    return ",
        "test": "assert add(2, 3) == 5\nassert add(-1, 1) == 0",
        "expected_prefix": "a + b",
    },
    {
        "prompt": "def square(x):\n    return ",
        "test": "assert square(4) == 16\nassert square(0) == 0",
        "expected_prefix": "x * x",
    },
    {
        "prompt": "def is_even(n):\n    return ",
        "test": "assert is_even(4) == True\nassert is_even(3) == False",
        "expected_prefix": "n % 2 == 0",
    },
    {
        "prompt": "def double(x):\n    return ",
        "test": "assert double(7) == 14\nassert double(-2) == -4",
        "expected_prefix": "x * 2",
    },
    {
        "prompt": "# Calculate 15 * 4\nresult = ",
        "test": "assert result == 60",
        "expected_prefix": "60",
    },
    {
        "prompt": "# Calculate 100 - 37\nresult = ",
        "test": "assert result == 63",
        "expected_prefix": "63",
    },
    {
        "prompt": "def identity(x):\n    return ",
        "test": "assert identity(42) == 42",
        "expected_prefix": "x",
    },
    {
        "prompt": "def negate(b):\n    return ",
        "test": "assert negate(True) == False\nassert negate(False) == True",
        "expected_prefix": "not b",
    },
]


def evaluate_completion_reward(prompt: str, completion: str, test_suite: str, expected_prefix: str) -> float:
    """
    Computes deterministic, verifiable reward:
    +2.0: Unit test passes in Python execution environment.
    +1.0: Valid AST parse (syntactically valid Python).
    +0.5: Matches expected analytical prefix.
    -0.5: SyntaxError or RuntimeError during test.
    """
    code = prompt + completion.split("\n")[0]  # First line completion
    reward = 0.0

    # 1. Syntax check
    try:
        ast.parse(code)
        reward += 0.5
    except SyntaxError:
        return -0.5

    # 2. Heuristic prefix check
    if completion.strip().startswith(expected_prefix):
        reward += 0.5

    # 3. Dynamic execution test
    exec_scope = {}
    try:
        exec(code + "\n" + test_suite, exec_scope)
        reward += 1.5
    except Exception:
        reward -= 0.2

    return reward


def train_grpo():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Starting IMF Verifiable GRPO on {device}...", flush=True)

    tok = CodeBPETokenizer.load("checkpoints/code_bpe_tokenizer.json")
    vocab_size = len(tok.vocab)

    # 1. Load Policy Model
    policy = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=256,
        num_layers=4,
        num_heads=8,
        polytope_dim=5,
        num_experts=32,
        top_k=4,
        max_seq_len=128,
        alpha_recon=0.3,
    ).to(device)
    policy_path = "checkpoints/imf_scaled_125m_omni118.pt"
    policy.load_state_dict(torch.load(policy_path, map_location=device))
    print(f"[✓] Policy Model loaded ({sum(p.numel() for p in policy.parameters()):,} params)", flush=True)

    # 2. Load Frozen Reference Model for KL Penalty
    ref_model = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=256,
        num_layers=4,
        num_heads=8,
        polytope_dim=5,
        num_experts=32,
        top_k=4,
        max_seq_len=128,
        alpha_recon=0.3,
    ).to(device)
    ref_model.load_state_dict(torch.load(policy_path, map_location=device))
    ref_model.eval()
    for p in ref_model.parameters():
        p.requires_grad = False
    print(f"[✓] Reference Model loaded and frozen", flush=True)

    optimizer = optim.AdamW(policy.parameters(), lr=2e-5, weight_decay=1e-2)
    G = 4               # Group size: 4 completions per prompt
    clip_eps = 0.2     # PPO clipping parameter
    beta_kl = 0.04     # KL divergence regularization penalty
    gen_len = 12       # Rollout generation length
    steps = 40         # GRPO update iterations
    start_t = time.perf_counter()

    for step in range(1, steps + 1):
        task = PROMPT_TASKS[(step - 1) % len(PROMPT_TASKS)]
        prompt = task["prompt"]
        test_suite = task["test"]
        expected_pref = task["expected_prefix"]

        p_ids = tok.encode(prompt)
        p_tensor = torch.tensor([p_ids], device=device).repeat(G, 1)  # [G, P]
        prompt_len = p_tensor.shape[1]

        # 1. Rollout Phase (G completions sampled with temperature=0.8)
        policy.eval()
        curr_seqs = p_tensor.clone()
        with torch.no_grad():
            for _ in range(gen_len):
                with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                    logits, _, _ = policy(curr_seqs)
                    next_tok = torch.multinomial(F.softmax(logits[:, -1, :] / 0.8, dim=-1), 1)
                curr_seqs = torch.cat([curr_seqs, next_tok], dim=1)

        # 2. Compute Verifiable Rewards & Relative Advantages
        rewards = []
        for i in range(G):
            gen_ids = curr_seqs[i, prompt_len:].tolist()
            gen_text = tok.decode(gen_ids)
            r = evaluate_completion_reward(prompt, gen_text, test_suite, expected_pref)
            rewards.append(r)

        r_tensor = torch.tensor(rewards, device=device, dtype=torch.float32)
        mean_r = r_tensor.mean()
        std_r = r_tensor.std(unbiased=False) + 1e-8
        advantages = (r_tensor - mean_r) / std_r  # [G]

        # 3. Policy & Reference Forward Passes on Completed Sequences
        inputs = curr_seqs[:, :-1]
        action_targets = curr_seqs[:, 1:]

        with torch.no_grad():
            with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                ref_logits, _, _ = ref_model(inputs)
                ref_log_p = F.log_softmax(ref_logits, dim=-1)
                ref_token_log_p = ref_log_p.gather(2, action_targets.unsqueeze(-1)).squeeze(-1)
                old_action_log_p = ref_token_log_p[:, prompt_len - 1:]

        # 4. Policy Update with GRPO Loss
        policy.train()
        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", dtype=torch.bfloat16):
            pol_logits, _, pol_metrics = policy(inputs)
            pol_log_p = F.log_softmax(pol_logits, dim=-1)
            pol_token_log_p = pol_log_p.gather(2, action_targets.unsqueeze(-1)).squeeze(-1)
            new_action_log_p = pol_token_log_p[:, prompt_len - 1:]

            # Token-level probability ratio
            ratio = torch.exp(new_action_log_p - old_action_log_p.detach())
            adv_expanded = advantages.unsqueeze(-1).expand_as(ratio)

            # PPO Clipped Surrogate
            surr1 = ratio * adv_expanded
            surr2 = torch.clamp(ratio, 1.0 - clip_eps, 1.0 + clip_eps) * adv_expanded
            policy_loss = -torch.min(surr1, surr2).mean()

            # Reverse KL penalty to reference model
            kl_div = (torch.exp(ref_token_log_p.detach() - pol_token_log_p) - 1.0) - (ref_token_log_p.detach() - pol_token_log_p)
            kl_loss = kl_div[:, prompt_len - 1:].mean()

            # Aux polytope reconstruction loss
            recon_loss = pol_metrics.get("loss_recon", torch.tensor(0.0, device=device))

            total_loss = policy_loss + beta_kl * kl_loss + 0.1 * recon_loss

        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
        optimizer.step()

        if step % 5 == 0 or step == steps:
            dt = time.perf_counter() - start_t
            print(
                f"GRPO Step {step:2d}/{steps} | "
                f"Mean Reward: {mean_r.item():+.3f} | "
                f"Loss: {total_loss.item():.4f} (Pol: {policy_loss.item():.4f}, KL: {kl_loss.item():.4f}) | "
                f"Elapsed: {dt:.1f}s",
                flush=True,
            )

    out_path = "checkpoints/imf_scaled_125m_grpo_rl.pt"
    torch.save(policy.state_dict(), out_path)
    print(f"[✓] Saved GRPO Reasoning Checkpoint to {out_path}", flush=True)


if __name__ == "__main__":
    train_grpo()
