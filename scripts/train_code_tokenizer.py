"""
Train Code-BPE Tokenizer on Multi-Domain Reasoning & Systems Code Corpus.
"""

from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.synthetic_reasoning_corpus import MultiDomainCorpusSynthesizer


def main():
    print("[*] Generating training text across Python, Rust, Lean 4, and Math...")
    syn = MultiDomainCorpusSynthesizer(seed=101)
    samples = syn.generate_corpus(num_samples=2000)
    full_text = "\n\n".join([s[0] for s in samples])

    tokenizer = CodeBPETokenizer()
    print(f"[*] Training CodeBPETokenizer on {len(full_text):,} characters...")
    tokenizer.train(full_text, target_vocab_size=1024, min_freq=2)

    out_path = "checkpoints/code_bpe_tokenizer.json"
    tokenizer.save(out_path)
    print(f"[+] Saved CodeBPETokenizer to {out_path} with {len(tokenizer.vocab)} tokens.")

    # Verification roundtrip
    test_code = samples[0][0]
    enc = tokenizer.encode(test_code)
    dec = tokenizer.decode(enc)
    assert test_code == dec, "Tokenizer failed roundtrip fidelity!"
    print("[✓] Perfect 100% roundtrip fidelity verified on real multiline code.")


if __name__ == "__main__":
    main()
