"""
Polytope MoPE Active Expert (Top-k) Empirical Ablation.
Evaluates the geometric expressivity and compute efficiency of routing across:
k in [1, 2, 4, 6] active experts per token on the 100-domain master manifold.
Measures:
1. Convergence loss & validation perplexity.
2. Latent representation entropy (measuring polyhedral expressivity vs redundancy).
3. Tokens/sec throughput on GPU.
"""

import time
import torch
import torch.nn as nn
import torch.optim as optim

from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.omni_100_master_synthesizer import Omni100MasterSynthesizer
from train_flagship_omnilm_mope import IMFOmniLMMoPE


def run_k_ablation():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Active Expert (Top-k) Polytope Ablation on {device}...")

    # Load Tokenizer
    tok_path = "checkpoints/code_bpe_tokenizer.json"
    tokenizer = CodeBPETokenizer.load(tok_path)
    vocab_size = len(tokenizer.vocab)

    # Synthesize multi-domain calibration data
    synthesizer = Omni100MasterSynthesizer(seed=42)
    corpus = synthesizer.generate_corpus(num_samples=600)
    
    # Tokenize corpus into batches
    token_batches = []
    for txt, _ in corpus:
        ids = tokenizer.encode(txt)
        if len(ids) >= 128:
            token_batches.append(ids[:128])
        if len(token_batches) >= 200:
            break
    
    data = torch.tensor(token_batches, dtype=torch.long, device=device) # [200, 128]
    train_x, train_y = data[:160, :-1], data[:160, 1:]
    val_x, val_y = data[160:, :-1], data[160:, 1:]

    k_candidates = [1, 2, 4, 6]
    results = {}

    for k in k_candidates:
        print(f"\n[>] Training Polytope-MoE with k={k} active experts (d=5 polytope complex)...")
        torch.manual_seed(101)
        
        model = IMFOmniLMMoPE(
            vocab_size=vocab_size,
            d_model=128,
            num_layers=2,
            num_heads=4,
            polytope_dim=5,
            num_experts=32,
            top_k=k,
            max_seq_len=128,
            alpha_recon=0.3,
        ).to(device)

        optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-2)
        criterion = nn.CrossEntropyLoss()

        start_t = time.perf_counter()
        model.train()
        
        # Train for 60 iterations
        for step in range(60):
            idx = step % (len(train_x) // 16)
            bx = train_x[idx*16:(idx+1)*16]
            by = train_y[idx*16:(idx+1)*16]

            optimizer.zero_grad()
            _, _, metrics = model(bx, targets=by)
            loss = metrics["total_loss"]
            loss.backward()
            optimizer.step()

        elapsed = time.perf_counter() - start_t
        throughput = (60 * 16 * 127) / elapsed

        # Validation evaluation
        model.eval()
        with torch.no_grad():
            _, _, val_metrics = model(val_x, targets=val_y)
            val_loss = val_metrics["loss_pred"].item()
            val_ppl = torch.exp(torch.tensor(val_loss)).item()
            
            # Compute routing entropy across tokens from layer 0
            # Run one forward pass to get aux dict
            tok_x = model.tok_embed(val_x) + model.pos_embed[:, :val_x.shape[1], :]
            omni_x = model.layers[0](tok_x)
            _, aux0 = model.moe_layers[0](omni_x)
            w = aux0["topk_weights"] # [B, T, k]
            w_clamped = torch.clamp(w, min=1e-9)
            entropy = -torch.sum(w_clamped * torch.log(w_clamped), dim=-1).mean().item()

        results[k] = {
            "val_loss": val_loss,
            "val_ppl": val_ppl,
            "entropy": entropy,
            "throughput": throughput,
            "time_s": elapsed
        }
        print(f"    Result k={k}: Val Loss={val_loss:.4f} | PPL={val_ppl:.2f} | Entropy={entropy:.4f} | Throughput={throughput:.1f} tok/s")

    print("\n" + "="*85)
    print(f"{'Active Experts (k)':<20} | {'Val Loss':<12} | {'Perplexity':<12} | {'Weight Entropy':<16} | {'Throughput'}")
    print("="*85)
    for k, r in results.items():
        print(f"k = {k:<16} | {r['val_loss']:<12.4f} | {r['val_ppl']:<12.2f} | {r['entropy']:<16.4f} | {r['throughput']:.1f} tok/s")
    print("="*85)

    return results

if __name__ == "__main__":
    run_k_ablation()
