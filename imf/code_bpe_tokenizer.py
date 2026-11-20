"""
Byte-Level BPE Tokenizer for Multi-Language Code and Reasoning (IMF).

Preserves exact whitespace, indentations, newlines (\\n), tabs (\\t),
and punctuation across Python, Rust, Lean 4, and Mathematics.
Operates natively on raw bytes / characters without destructive .split() calls.
"""

from collections import Counter
import json
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple, Union


class CodeBPETokenizer:
    """Exact whitespace-preserving Byte/Char BPE Tokenizer for Code and Formal Proofs."""

    def __init__(
        self,
        vocab: Optional[Dict[str, int]] = None,
        merges: Optional[List[Tuple[str, str]]] = None,
    ):
        self.special_tokens = ["<pad>", "<unk>", "<bos>", "<eos>"]
        if vocab is not None and merges is not None:
            self.vocab = vocab
            self.inverse_vocab = {int(v): k for k, v in vocab.items()}
            self.merges = [tuple(m) for m in merges]
        else:
            self.vocab = {tok: idx for idx, tok in enumerate(self.special_tokens)}
            self.inverse_vocab = {idx: tok for tok, idx in self.vocab.items()}
            self.merges = []
        self._bpe_ranks = {pair: i for i, pair in enumerate(self.merges)}

    @property
    def pad_id(self) -> int:
        return self.vocab["<pad>"]

    @property
    def unk_id(self) -> int:
        return self.vocab["<unk>"]

    @property
    def bos_id(self) -> int:
        return self.vocab["<bos>"]

    @property
    def eos_id(self) -> int:
        return self.vocab["<eos>"]

    def _get_stats(self, split_words: Dict[Tuple[str, ...], int]) -> Counter:
        pairs = Counter()
        for word, freq in split_words.items():
            for i in range(len(word) - 1):
                pairs[(word[i], word[i + 1])] += freq
        return pairs

    def _merge_vocab(
        self, pair: Tuple[str, str], split_words: Dict[Tuple[str, ...], int]
    ) -> Dict[Tuple[str, ...], int]:
        new_split_words = {}
        first, second = pair
        for word, freq in split_words.items():
            new_word = []
            i = 0
            while i < len(word):
                if i < len(word) - 1 and word[i] == first and word[i + 1] == second:
                    new_word.append(first + second)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            new_split_words[tuple(new_word)] = freq
        return new_split_words

    def _pre_tokenize(self, text: str) -> List[str]:
        """Preserves newlines, spaces, indentation, and symbols exactly."""
        # Non-destructive regex: splits into sequences of alphanumeric or whitespace or symbols
        tokens = re.findall(r"\n+|\s+|[a-zA-Z0-9_]+|[^\s\w]", text)
        return tokens

    def train(self, text: str, target_vocab_size: int = 1024, min_freq: int = 2):
        self.vocab = {tok: idx for idx, tok in enumerate(self.special_tokens)}
        self.merges = []

        segments = self._pre_tokenize(text)
        seg_counts = Counter(segments)

        split_words = {tuple(list(seg)): freq for seg, freq in seg_counts.items()}

        # Seed character alphabet
        chars = sorted(list({char for seg in split_words for char in seg}))
        for char in chars:
            if char not in self.vocab:
                self.vocab[char] = len(self.vocab)

        num_merges = target_vocab_size - len(self.vocab)
        for _ in range(max(0, num_merges)):
            pairs = self._get_stats(split_words)
            if not pairs:
                break
            best_pair, freq = pairs.most_common(1)[0]
            if freq < min_freq:
                break

            split_words = self._merge_vocab(best_pair, split_words)
            merged = best_pair[0] + best_pair[1]
            if merged not in self.vocab:
                self.vocab[merged] = len(self.vocab)
            self.merges.append(best_pair)

        self.inverse_vocab = {idx: tok for tok, idx in self.vocab.items()}

    def encode(self, text: str, add_special_tokens: bool = False) -> List[int]:
        tokens = []
        if add_special_tokens:
            tokens.append(self.bos_id)

        segments = self._pre_tokenize(text)
        for seg in segments:
            seg_tuple = tuple(list(seg))
            if len(seg_tuple) > 1 and self._bpe_ranks:
                while True:
                    min_rank = float("inf")
                    best_pair = None
                    for i in range(len(seg_tuple) - 1):
                        p = (seg_tuple[i], seg_tuple[i + 1])
                        r = self._bpe_ranks.get(p, float("inf"))
                        if r < min_rank:
                            min_rank = r
                            best_pair = p
                    if min_rank == float("inf"):
                        break
                    first, second = best_pair
                    merged = first + second
                    new_seg = []
                    i = 0
                    while i < len(seg_tuple):
                        if i < len(seg_tuple) - 1 and seg_tuple[i] == first and seg_tuple[i + 1] == second:
                            new_seg.append(merged)
                            i += 2
                        else:
                            new_seg.append(seg_tuple[i])
                            i += 1
                    seg_tuple = tuple(new_seg)

            tokens.extend([self.vocab.get(sym, self.unk_id) for sym in seg_tuple])

        if add_special_tokens:
            tokens.append(self.eos_id)
        return tokens

    def decode(self, indices: List[int]) -> str:
        tokens = [self.inverse_vocab.get(idx, "") for idx in indices]
        filtered = [tok for tok in tokens if tok not in self.special_tokens]
        # Invert exactly without stripping spaces or newlines
        return "".join(filtered)

    def save(self, filepath: Union[str, Path]):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "vocab": self.vocab,
            "merges": [list(m) for m in self.merges],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> "CodeBPETokenizer":
        path = Path(filepath)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(vocab=data["vocab"], merges=data["merges"])
