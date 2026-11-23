"""
Evaluation harness for testing IMF-MoPE on Multi-Domain Reasoning:
- Code Syntax & Control Flow (Python/Rust)
- Formal Logic Proofs (Lean 4 Tactic Transitions)
- Multi-step Symbolic Chain-of-Thought (GSM8k-style Arithmetic)
"""

import math
import torch
import torch.nn.functional as F

from train_mope_reasoning import IMFMiniMoPELM
from imf.bpe_tokenizer import BPETokenizer
from imf.synthetic_reasoning_corpus import MultiDomainCorpusSynthesizer


def evaluate_mope_reasoning():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running MoPE Multi-Domain Reasoning Evaluation on {device}...")

    # Load Tokenizer & Model
    tok_path = "checkpoints/bpe_tokenizer_reasoning.pt"
    tokenizer = BPETokenizer.load(tok_path)
    vocab_size = len(tokenizer.vocab)

    model = IMFMiniMoPELM(
        vocab_size=vocab_size,
        d_model=128,
        num_layers=2,
        num_experts=4,
        top_k=2,
        max_seq_len=128,
    ).to(device)

    ckpt_path = "checkpoints/imf_mope_reasoning.pt"
    model.load_state_dict(torch.load(ckpt_path, map_location=device, weights_only=True))
    model.eval()

    synthesizer = MultiDomainCorpusSynthesizer(seed=999)

    domains = {
        "Python Code": [synthesizer.generate_python_sample() for _ in range(25)],
        "Rust Systems": [synthesizer.generate_rust_sample() for _ in range(25)],
        "Lean 4 Formal Logic": [synthesizer.generate_lean4_sample() for _ in range(25)],
        "Symbolic CoT Math": [synthesizer.generate_math_cot_sample() for _ in range(25)],
    }

    results = {}
    print(f"\n{'Domain':<22} | {'Perplexity':<12} | {'Top-1 Acc':<10} | {'Top-5 Acc':<10}")
    print("-" * 62)

    with torch.no_grad():
        for domain, samples in domains.items():
            total_loss = 0.0
            total_tokens = 0
            correct_top1 = 0
            correct_top5 = 0

            for text in samples:
                tokens = tokenizer.encode(text)
                if len(tokens) < 4:
                    continue
                tokens = tokens[:128]
                x = torch.tensor([tokens[:-1]], dtype=torch.long, device=device)
                y = torch.tensor([tokens[1:]], dtype=torch.long, device=device)

                logits, _ = model(x)
                loss = F.cross_entropy(logits.reshape(-1, vocab_size), y.reshape(-1), reduction="sum")

                total_loss += loss.item()
                total_tokens += y.numel()

                preds = logits.squeeze(0) # [T-1, V]
                top1 = preds.argmax(dim=-1)
                correct_top1 += (top1 == y.squeeze(0)).sum().item()

                _, top5 = preds.topk(5, dim=-1)
                correct_top5 += (top5 == y.squeeze(0).unsqueeze(-1)).any(dim=-1).sum().item()

            avg_loss = total_loss / max(total_tokens, 1)
            ppl = math.exp(min(avg_loss, 20.0))
            top1_acc = (correct_top1 / max(total_tokens, 1)) * 100
            top5_acc = (correct_top5 / max(total_tokens, 1)) * 100

            results[domain] = {"PPL": ppl, "Top-1": top1_acc, "Top-5": top5_acc}
            print(f"{domain:<22} | {ppl:<12.2f} | {top1_acc:<9.1f}% | {top5_acc:<9.1f}%")

    print("-" * 62)
    return results


if __name__ == "__main__":
    evaluate_mope_reasoning()
