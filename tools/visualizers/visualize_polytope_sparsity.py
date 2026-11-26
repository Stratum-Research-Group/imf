"""
visualize_polytope_sparsity.py
Analyzes and visualizes Barycentric Coordinate Sparsity across Polytope Landmark Vertices:
1. Computes Shannon Entropy H(w) = -sum(w_i * log(w_i + eps)) and Normalized Entropy H(w)/log(K).
2. Computes Gini Coefficient G(w) = sum_i sum_j |w_i - w_j| / (2 * K^2 * mu) to measure vertex specialization.
3. Tracks vertex coordinate dynamics over autoregressive token generation steps in ScaledIMFDecoderLM.
4. Generates publication-grade plot: assets/polytope_sparsity_dynamics.png.
"""

import math
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F

from imf.bpe_tokenizer import BPETokenizer
from train_scaled_imf import ScaledIMFDecoderLM

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
OUTPUT_DIR = Path("assets")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def compute_shannon_entropy(coords: torch.Tensor, eps: float = 1e-9) -> torch.Tensor:
    """
    Computes Shannon entropy across the vertex dimension.
    coords: [..., K] normalized probability distribution summing to 1.
    """
    p = coords.clamp(min=eps)
    entropy = -torch.sum(p * torch.log(p), dim=-1)
    K = coords.shape[-1]
    norm_entropy = entropy / math.log(K)
    return norm_entropy


def compute_gini_coefficient(coords: torch.Tensor) -> torch.Tensor:
    """
    Computes the Gini inequality coefficient across the vertex dimension.
    coords: [..., K]. Returns values in [0, 1] (0 = uniform equal distribution, 1 = concentrated on 1 vertex).
    """
    # Sort coords along last dimension
    sorted_coords, _ = torch.sort(coords, dim=-1)
    K = coords.shape[-1]
    index = torch.arange(1, K + 1, device=coords.device, dtype=coords.dtype)
    n = K
    # Gini formula for non-negative sum=1 vectors: (2 * sum(i * y_i) - (n + 1)) / (n - 1)
    weighted_sum = torch.sum(sorted_coords * index, dim=-1)
    gini = (2.0 * weighted_sum - (n + 1.0)) / (n - 1.0)
    return gini.clamp(min=0.0, max=1.0)


def analyze_model_sparsity(
    checkpoint_path: Path = Path("imf_tinystories_checkpoint.pt"),
    tokenizer_path: Path = Path("data/tinystories_bpe.json"),
    prompt: str = "Once upon a time, a brave little knight found a magical key hidden inside the hollow tree.",
    steps_to_generate: int = 50,
):
    print("=" * 85)
    print("POLYTOPE LANDMARK BARYCENTRIC SPARSITY ANALYSIS")
    print(f"Device: {DEVICE} | Prompt: {prompt[:40]}...")
    print("=" * 85)

    if not tokenizer_path.exists():
        raise FileNotFoundError(f"Missing tokenizer at {tokenizer_path}")
    tokenizer = BPETokenizer.load(str(tokenizer_path))

    model = ScaledIMFDecoderLM(
        vocab_size=tokenizer.vocab_size,
        d_model=256,
        num_heads=8,
        n_layers=6,
        preset="decayotton_orthoplex"
    ).to(DEVICE)

    if checkpoint_path.exists():
        ckpt = torch.load(checkpoint_path, map_location=DEVICE)
        state = ckpt["model_state"] if "model_state" in ckpt else ckpt.get("model", ckpt)
        model.load_state_dict(state)
        print(f"[*] Loaded trained model from {checkpoint_path}")
    else:
        print("[!] Warning: Checkpoint not found; using initialized weights.")

    model.eval()

    prompt_ids = tokenizer.encode(prompt)
    if not prompt_ids:
        prompt_ids = [0]

    # Collect coordinates across all layers during autoregressive generation
    all_layer_coords = [[] for _ in range(model.blocks.__len__())]
    all_tokens = list(prompt_ids)

    states = model.init_streaming_states(1, DEVICE)

    with torch.no_grad():
        # Prime on prompt
        for tid in prompt_ids[:-1]:
            tok_t = torch.tensor([tid], device=DEVICE)
            _, states = model.generate_step(tok_t, states)

        cur_tok = torch.tensor([prompt_ids[-1]], device=DEVICE)

        for _ in range(steps_to_generate):
            # Extract coordinates for each block's connector
            for layer_idx, block in enumerate(model.blocks):
                x_embed = model.tok_embed(cur_tok).unsqueeze(0)  # [1, 1, d_model]
                coords = block.savg.connector.get_coordinates(x_embed).squeeze(0).squeeze(0)  # [K]
                all_layer_coords[layer_idx].append(coords.cpu().numpy())

            logits, states = model.generate_step(cur_tok, states)
            probs = torch.softmax(logits / 0.8, dim=-1)
            next_id = torch.multinomial(probs, num_samples=1).item()
            all_tokens.append(next_id)
            cur_tok = torch.tensor([next_id], device=DEVICE)

    print(f"[+] Successfully tracked {steps_to_generate} autoregressive generation steps.")

    # Convert to numpy: [n_layers, steps, K]
    layer_coords = np.array(all_layer_coords)
    n_layers, n_steps, K = layer_coords.shape

    # Compute metric curves across steps
    tensor_coords = torch.tensor(layer_coords, device=DEVICE)
    norm_entropy = compute_shannon_entropy(tensor_coords).cpu().numpy()  # [n_layers, steps]
    gini_coeffs = compute_gini_coefficient(tensor_coords).cpu().numpy()  # [n_layers, steps]

    mean_entropy = np.mean(norm_entropy, axis=1)
    mean_gini = np.mean(gini_coeffs, axis=1)

    print("\nLayer-wise Barycentric Sparsity Summary (Decayotton 20 Vertices):")
    print(f"{'Layer':<10} | {'Mean Norm Entropy':<20} | {'Mean Gini Coefficient':<25} | {'Interpretation':<20}")
    print("-" * 80)
    for l in range(n_layers):
        status = "Highly Specialized" if mean_gini[l] > 0.6 else ("Moderately Sparse" if mean_gini[l] > 0.4 else "Distributed")
        print(f"Layer {l:<4} | {mean_entropy[l]:<20.4f} | {mean_gini[l]:<25.4f} | {status:<20}")

    # Generate Publication Plot
    try:
        import matplotlib.pyplot as plt

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.0), constrained_layout=True)

        steps = np.arange(1, n_steps + 1)
        colors = plt.cm.viridis(np.linspace(0.1, 0.9, n_layers))

        for l in range(n_layers):
            ax1.plot(steps, norm_entropy[l], label=f"Layer {l}", color=colors[l], linewidth=1.8, alpha=0.85)
            ax2.plot(steps, gini_coeffs[l], label=f"Layer {l}", color=colors[l], linewidth=1.8, alpha=0.85)

        ax1.set_title("Normalized Shannon Entropy H(w)/log(K)", fontsize=12, fontweight="bold")
        ax1.set_xlabel("Autoregressive Token Step", fontsize=11)
        ax1.set_ylabel("Normalized Entropy (Lower = Sharper)", fontsize=11)
        ax1.set_ylim(0.0, 1.05)
        ax1.grid(True, linestyle="--", alpha=0.4)
        ax1.legend(loc="lower right", fontsize=9, ncol=2)

        ax2.set_title("Gini Inequality Coefficient G(w)", fontsize=12, fontweight="bold")
        ax2.set_xlabel("Autoregressive Token Step", fontsize=11)
        ax2.set_ylabel("Gini Coefficient (Higher = More Specialized)", fontsize=11)
        ax2.set_ylim(0.0, 1.05)
        ax2.grid(True, linestyle="--", alpha=0.4)
        ax2.legend(loc="upper right", fontsize=9, ncol=2)

        plot_path = OUTPUT_DIR / "polytope_sparsity_dynamics.png"
        plt.savefig(plot_path, dpi=200)
        plt.close()
        print(f"\n[✓] Saved publication plot to {plot_path}")
    except Exception as e:
        print(f"[!] Warning: Matplotlib plot generation failed: {e}")


if __name__ == "__main__":
    analyze_model_sparsity()
