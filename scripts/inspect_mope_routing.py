"""
Inspect Polytope Mixture-of-Polytope-Experts (MoPE) Routing across Specialized Domains.
Evaluates the geometric routing distribution across Quantum Mathematics, Chaos Theory,
Game Theory, Cyber Security, Systems, Genomics, and Formal Logic.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch
from imf.code_bpe_tokenizer import CodeBPETokenizer
from train_flagship_omnilm_mope import IMFOmniLMMoPE


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Loading Flagship IMF-OmniLM-MoPE checkpoint on {device}...")

    tok_path = "checkpoints/code_bpe_tokenizer.json"
    tokenizer = CodeBPETokenizer.load(tok_path)
    vocab_size = len(tokenizer.vocab)

    # Instantiating Flagship architecture configuration
    model = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=128,
        num_layers=2,
        num_heads=4,
        polytope_dim=5,
        num_experts=32,
        top_k=2,
        max_seq_len=256,
        alpha_recon=0.3,
    ).to(device)

    ckpt_path = "checkpoints/imf_omnilm_mope_flagship.pt"
    state_dict = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    test_queries = [
        ("Quantum Circuit", "qreg = QuantumRegister(3)\ncircuit.h(0)\ncircuit.cx(0, 1)"),
        ("Chaos Theory", "dx = sigma * (y - x)\ndy = x * (rho - z) - y\nlyapunov_exponent = 0.9056"),
        ("Game Theory", "payoff_matrix = np.array([[3, 0], [5, 1]])\nnash_equilibrium = compute_nash()"),
        ("Cyber Security ROP", "pop_rdi = 0x40123b\nret = 0x40101a\npayload = b'A'*56 + p64(pop_rdi)"),
        ("Systems Rust/eBPF", "#[no_mangle]\npub unsafe extern \"C\" fn kprobe_sys_execve(ctx: *mut c_void) -> i32"),
        ("Formal Logic Lean 4", "theorem nat_add_comm (a b : Nat) : a + b = b + a := by\n  induction b with\n  | zero => rfl"),
        ("Genomics CRISPR", "chr7:55181378-55181400:PAM_NGG gRNA: GAGTTCTTGCTCTTCATCGA"),
        ("Multilingual NLP", "en: The algorithm converges in polynomial time. -> fr: L'algorithme converge en temps polynomial.")
    ]

    print("\n" + "="*85)
    print(f"{'Domain Query':<22} | {'Top-1 Expert':<14} | {'Top-1 Weight':<13} | {'Top-2 Expert':<14} | {'Top-2 Weight'}")
    print("="*85)

    for domain_label, query in test_queries:
        token_ids = tokenizer.encode(query)
        if len(token_ids) > 256:
            token_ids = token_ids[:256]
        elif len(token_ids) == 0:
            continue
        
        inp = torch.tensor([token_ids], dtype=torch.long, device=device)
        with torch.no_grad():
            x = model.tok_embed(inp)
            # Run through layer 0 MoPE
            _, aux = model.moe_layers[0](x)
            weights = aux["topk_weights"]
            indices = aux["topk_indices"]
            
            # weights: (1, seq_len, top_k), indices: (1, seq_len, top_k)
            avg_w = weights[0].mean(dim=0).cpu().tolist()
            # Most frequent top-1 expert across tokens
            top1_tokens = indices[0, :, 0].cpu().tolist()
            top2_tokens = indices[0, :, 1].cpu().tolist()
            top1_exp = max(set(top1_tokens), key=top1_tokens.count)
            top2_exp = max(set(top2_tokens), key=top2_tokens.count)
            
            print(f"{domain_label:<22} | Expert #{top1_exp:<7} | {avg_w[0]:<13.4f} | Expert #{top2_exp:<7} | {avg_w[1]:<12.4f}")

    print("="*85)
    print("[+] Geometric routing evaluation completed successfully.")


if __name__ == "__main__":
    main()
