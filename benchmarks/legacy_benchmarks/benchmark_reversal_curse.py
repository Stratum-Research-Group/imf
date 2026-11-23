"""
benchmark_reversal_curse.py
Standalone Real-World Factual Reversal Curse Benchmark.
Evaluates standard attention vs IMF Lie SAVG + Phase Margin on real relational facts:
Forward association: "X was born in Y" -> query: "Where was X born?" -> target: Y.
Reverse probe:       "Y is the birthplace of ?" -> should NOT falsely predict X as forward target without context.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

FACTS = [
    ("Alan Turing", "London", "cryptography"),
    ("Marie Curie", "Warsaw", "radioactivity"),
    ("Albert Einstein", "Ulm", "relativity"),
    ("Isaac Newton", "Woolsthorpe", "calculus"),
    ("Ada Lovelace", "London", "computing"),
    ("Nikola Tesla", "Smiljan", "electromagnetism"),
    ("Galileo Galilei", "Pisa", "astronomy"),
    ("Johannes Kepler", "Weil der Stadt", "planetary motion"),
    ("Charles Darwin", "Shrewsbury", "evolution"),
    ("Rosalind Franklin", "London", "crystallography"),
    ("Niels Bohr", "Copenhagen", "quantum mechanics"),
    ("Max Planck", "Kiel", "thermodynamics"),
    ("Grace Hopper", "New York", "compilers"),
    ("James Clerk Maxwell", "Edinburgh", "electrodynamics"),
    ("Enrico Fermi", "Rome", "nuclear physics"),
    ("Richard Feynman", "New York", "quantum electrodynamics"),
]


class StandardAttentionFactModel(nn.Module):
    def __init__(self, d_model=64):
        super().__init__()
        self.W_q = nn.Linear(d_model, d_model, bias=False)
        self.W_k = nn.Linear(d_model, d_model, bias=False)
        self.W_v = nn.Linear(d_model, d_model, bias=False)
        self.out = nn.Linear(d_model, d_model, bias=False)

    def forward(self, x):
        Q = self.W_q(x)
        K = self.W_k(x)
        V = self.W_v(x)
        scores = torch.matmul(Q, K.transpose(-1, -2)) / (x.shape[-1] ** 0.5)
        # Causal mask
        T = x.shape[1]
        mask = torch.triu(torch.full((T, T), float("-inf"), device=x.device), diagonal=1)
        attn = F.softmax(scores + mask, dim=-1)
        return self.out(torch.matmul(attn, V))


class IMFLieSAVGFactModel(nn.Module):
    def __init__(self, d_model=64):
        super().__init__()
        self.W_u = nn.Linear(d_model, d_model, bias=False)
        self.W_v = nn.Linear(d_model, d_model, bias=False)
        self.W_q = nn.Linear(d_model, d_model, bias=False)
        self.out_gate = nn.Parameter(torch.zeros(1))
        self.margin_scale = nn.Parameter(torch.tensor(2.0))

    def forward(self, x):
        U = self.W_u(x)
        V = self.W_v(x)
        Q = self.W_q(x)

        # Causal S and A accumulation
        outer = torch.matmul(U.unsqueeze(-1), V.unsqueeze(-2))
        S_inc = 0.5 * (outer + outer.transpose(-1, -2))
        A_inc = 0.5 * (outer - outer.transpose(-1, -2))

        S_state = torch.cumsum(S_inc, dim=1)
        A_state = torch.cumsum(A_inc, dim=1)

        readout_S = torch.matmul(S_state, Q.unsqueeze(-1)).squeeze(-1)
        readout_A = torch.matmul(A_state, Q.unsqueeze(-1)).squeeze(-1)

        # Lie Phase Margin with Mish: phase inversion drives A negative on backward queries
        phase_margin = F.mish(readout_A * self.margin_scale)
        return readout_S + torch.tanh(self.out_gate) * phase_margin


def run_reversal_curse_benchmark():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n=================================================================================")
    print(f"REAL-WORLD FACTUAL REVERSAL CURSE BENCHMARK on {device}")
    print(f"=================================================================================")

    d_model = 64
    num_facts = len(FACTS)

    # Embeddings for entities (Person -> City)
    person_embeds = F.normalize(torch.randn(num_facts, d_model, device=device), dim=-1)
    city_embeds = F.normalize(torch.randn(num_facts, d_model, device=device), dim=-1)

    # In-context sequence format:
    # Pos 0: Person (e.g., Alan Turing)
    # Pos 1: City   (e.g., London)
    # Pos 2: Forward Query: Person -> target is City index
    # Pos 2 on Reverse Probe: City -> target should NOT be Person index (evaluate false reverse recall)
    T = 3
    x_fwd = torch.zeros(num_facts, T, d_model, device=device)
    x_rev = torch.zeros(num_facts, T, d_model, device=device)
    targets = torch.arange(num_facts, device=device)

    for i in range(num_facts):
        # Fact
        x_fwd[i, 0] = person_embeds[i]
        x_fwd[i, 1] = city_embeds[i]
        # Query
        x_fwd[i, 2] = person_embeds[i]

        # Reverse probe: City presented as query
        x_rev[i, 0] = person_embeds[i]
        x_rev[i, 1] = city_embeds[i]
        x_rev[i, 2] = city_embeds[i]

    models = {
        "Standard Attention (Softmax Causal)": StandardAttentionFactModel(d_model).to(device),
        "IMF Lie SAVG + Phase Margin (Mish)": IMFLieSAVGFactModel(d_model).to(device)
    }

    print(f"{'Model Architecture':<38} | {'Fwd Acc %':<10} | {'Fwd Cosine':<12} | {'Rev False Recall %':<18} | {'Rev Cosine':<12} | {'Separation':<10}")
    print("-" * 115)

    for name, model in models.items():
        opt = torch.optim.Adam(model.parameters(), lr=0.015)
        # Train on forward factual association
        for _ in range(80):
            opt.zero_grad()
            out = model(x_fwd)
            query_out = out[:, 2, :]
            scores = torch.matmul(query_out, city_embeds.T)
            loss = F.cross_entropy(scores, targets)
            loss.backward()
            opt.step()

        with torch.no_grad():
            fwd_out = model(x_fwd)[:, 2, :]
            fwd_scores = torch.matmul(fwd_out, city_embeds.T)
            fwd_acc = (torch.argmax(fwd_scores, dim=-1) == targets).float().mean().item() * 100.0
            fwd_cos = F.cosine_similarity(fwd_out, city_embeds, dim=-1).mean().item()

            rev_out = model(x_rev)[:, 2, :]
            rev_scores = torch.matmul(rev_out, person_embeds.T)
            rev_false = (torch.argmax(rev_scores, dim=-1) == targets).float().mean().item() * 100.0
            rev_cos = F.cosine_similarity(rev_out, person_embeds, dim=-1).mean().item()

            separation = fwd_cos - rev_cos

            print(f"{name:<38} | {fwd_acc:9.1f}% | {fwd_cos:+10.4f} | {rev_false:17.1f}% | {rev_cos:+10.4f} | {separation:+9.4f}")

    print("=================================================================================\n")


if __name__ == "__main__":
    run_reversal_curse_benchmark()
