"""
pretrain_imf_lm.py
Lightweight language modeling pretraining harness demonstrating end-to-end
training of a sub-quadratic decoder with FusedSAVGLayer on causal next-token prediction.
"""

import time
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf import FusedSAVGLayer, ConfigurablePolytopeConnector


class IMFDecoderBlock(nn.Module):
    """Transformer-style decoder block with FusedSAVGLayer replacing quadratic self-attention."""
    def __init__(self, d_model: int, d_ff: int = None, preset: str = "decayotton_orthoplex"):
        super().__init__()
        if d_ff is None:
            d_ff = 4 * d_model
        self.ln1 = nn.LayerNorm(d_model)
        self.savg = FusedSAVGLayer(d_model=d_model, preset=preset)
        self.ln2 = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Linear(d_ff, d_model)
        )

    def forward(self, x: torch.Tensor, use_triton: bool = True) -> torch.Tensor:
        # Pre-LN residual stream
        x = x + self.savg(self.ln1(x), use_triton=use_triton)
        x = x + self.mlp(self.ln2(x))
        return x

    def step(self, x_t: torch.Tensor, state, use_triton: bool = True):
        norm_x = self.ln1(x_t)
        savg_out, next_state = self.savg.step(norm_x, state, use_triton=use_triton)
        x_t = x_t + savg_out
        x_t = x_t + self.mlp(self.ln2(x_t))
        return x_t, next_state


class IMFLanguageModel(nn.Module):
    """Causal Autoregressive Language Model using IMF Memory Layers."""
    def __init__(
        self,
        vocab_size: int = 50257,
        d_model: int = 128,
        n_layers: int = 4,
        preset: str = "decayotton_orthoplex"
    ):
        super().__init__()
        self.d_model = d_model
        self.tok_embed = nn.Embedding(vocab_size, d_model)
        self.blocks = nn.ModuleList([
            IMFDecoderBlock(d_model=d_model, preset=preset)
            for _ in range(n_layers)
        ])
        self.ln_f = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

        # Weight tying
        self.lm_head.weight = self.tok_embed.weight

    def forward(self, input_ids: torch.Tensor, use_triton: bool = True) -> torch.Tensor:
        x = self.tok_embed(input_ids)
        for block in self.blocks:
            x = block(x, use_triton=use_triton)
        x = self.ln_f(x)
        logits = self.lm_head(x)
        return logits

    def init_streaming_states(self, batch_size: int, device: torch.device):
        return [b.savg.init_state(batch_size, device) for b in self.blocks]

    def generate_step(self, token_t: torch.Tensor, states, use_triton: bool = True):
        x = self.tok_embed(token_t)
        next_states = []
        for i, block in enumerate(self.blocks):
            x, next_st = block.step(x, states[i], use_triton=use_triton)
            next_states.append(next_st)
        x = self.ln_f(x)
        logits = self.lm_head(x)
        return logits, next_states


def run_pretrain_demo():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 80)
    print(f"IMF LANGUAGE MODEL PRETRAINING & GENERATION DEMO on {device}")
    print("=" * 80)

    vocab_size = 1000
    d_model = 64
    n_layers = 2
    batch_size = 8
    seq_len = 128
    num_steps = 30

    model = IMFLanguageModel(
        vocab_size=vocab_size,
        d_model=d_model,
        n_layers=n_layers,
        preset="decayotton_orthoplex"
    ).to(device)

    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)

    print(f"[*] Training model ({sum(p.numel() for p in model.parameters()):,} parameters)...")
    model.train()
    t0 = time.perf_counter()

    for step in range(1, num_steps + 1):
        # Synthetic causal text tokens
        tokens = torch.randint(0, vocab_size, (batch_size, seq_len), device=device)
        targets = torch.roll(tokens, shifts=-1, dims=1)
        targets[:, -1] = -100  # mask last target

        opt.zero_grad()
        logits = model(tokens, use_triton=True)
        loss = F.cross_entropy(logits.view(-1, vocab_size), targets.view(-1), ignore_index=-100)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

        if step % 10 == 0 or step == 1:
            print(f"  Step {step:2d}/{num_steps} | Loss: {loss.item():.4f}")

    total_time = (time.perf_counter() - t0) * 1000
    print(f"[+] Pretraining loop verified ({total_time:.1f} ms total, {total_time/num_steps:.2f} ms/step)")

    # Test O(1) Streaming Generation
    print("\n[*] Testing O(1) Streaming Autoregressive Generation...")
    model.eval()
    states = model.init_streaming_states(batch_size=1, device=device)
    curr_token = torch.tensor([[42]], device=device)

    generated = [42]
    with torch.no_grad():
        for _ in range(16):
            logits, states = model.generate_step(curr_token.squeeze(1), states, use_triton=True)
            next_tok = torch.argmax(logits, dim=-1, keepdim=True)
            generated.append(next_tok.item())
            curr_token = next_tok

    print(f"✓ Generated 16 tokens via O(1) recurrent step: {generated[:8]}...")
    print("=" * 80)


if __name__ == "__main__":
    run_pretrain_demo()
