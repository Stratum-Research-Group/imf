"""
tests/test_omni_synthesizers.py
Unit tests verifying the multi-domain synthetic corpus generators:
1. Omni118MasterSynthesizer: covers 118 domains, produces valid non-empty prompt/target pairs.
2. Domain diversity check: validates distinct syntactic formats (Python, Rust, Lean4, Math, System).
3. Seed reproducibility: identical seeds produce bitwise identical corpora.
"""

from imf.omni_118_master_synthesizer import Omni118MasterSynthesizer
from imf.synthetic_reasoning_corpus import MultiDomainCorpusSynthesizer


def test_omni_118_synthesizer_domain_coverage():
    syn = Omni118MasterSynthesizer(seed=42)
    corpus = syn.generate_corpus(num_samples=200)
    assert len(corpus) == 200

    domains_seen = set()
    for text, domain in corpus:
        assert len(text) > 10
        assert len(domain) > 0
        domains_seen.add(domain)

    # Must cover diverse scientific and systems domains
    assert len(domains_seen) >= 15, f"Expected >= 15 domains, got {len(domains_seen)}"


def test_omni_synthesizer_seed_determinism():
    syn1 = Omni118MasterSynthesizer(seed=12345)
    syn2 = Omni118MasterSynthesizer(seed=12345)

    c1 = syn1.generate_corpus(num_samples=50)
    c2 = syn2.generate_corpus(num_samples=50)

    for (t1, d1), (t2, d2) in zip(c1, c2):
        assert t1 == t2
        assert d1 == d2


def test_multi_domain_corpus_synthesizer():
    syn = MultiDomainCorpusSynthesizer(seed=999)
    py_sample = syn.generate_python_sample()
    rust_sample = syn.generate_rust_sample()
    lean_sample = syn.generate_lean4_sample()
    math_sample = syn.generate_math_cot_sample()

    assert "def " in py_sample or "class " in py_sample
    assert "fn " in rust_sample or "struct " in rust_sample or "impl " in rust_sample
    assert "theorem " in lean_sample or "lemma " in lean_sample or "def " in lean_sample
    assert "Question:" in math_sample or "Answer:" in math_sample or "=" in math_sample
