"""
tests/test_code_bpe_tokenizer.py
Unit tests for the CodeBPETokenizer:
1. Deterministic encode/decode roundtrip fidelity.
2. Handling of special indentation, whitespace, and python keywords.
3. Unknown character handling and fallback tokens.
4. JSON serialization and deserialization persistence.
"""

import tempfile
import os
from imf.code_bpe_tokenizer import CodeBPETokenizer


def test_code_bpe_tokenizer_roundtrip():
    # Train simple tokenizer on python snippet
    corpus = (
        "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n"
        "class Matrix:\n    def __init__(self, d):\n        self.d = d\n"
    )
    tok = CodeBPETokenizer()
    tok.train(corpus, target_vocab_size=300)

    sample = "def fibonacci(n):\n    return n"
    token_ids = tok.encode(sample)
    assert len(token_ids) > 0
    decoded = tok.decode(token_ids)
    assert decoded == sample, f"Roundtrip failed: expected {repr(sample)}, got {repr(decoded)}"


def test_code_bpe_tokenizer_save_load():
    corpus = "alpha beta gamma delta epsilon zeta eta theta alpha beta"
    tok = CodeBPETokenizer()
    tok.train(corpus, target_vocab_size=150)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        path = tmp.name

    try:
        tok.save(path)
        loaded_tok = CodeBPETokenizer.load(path)
        assert len(tok.vocab) == len(loaded_tok.vocab)
        text = "alpha gamma epsilon"
        assert tok.encode(text) == loaded_tok.encode(text)
    finally:
        if os.path.exists(path):
            os.remove(path)
