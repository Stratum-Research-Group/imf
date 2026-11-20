"""
imf/bpe_tokenizer.py
Lightweight, self-contained Byte-Pair Encoding (BPE) subword tokenizer.
Zero external dependencies beyond standard library and torch.
Supports training on raw text, serialization to JSON, subword encoding, and decoding.
"""

from collections import Counter
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


class BPETokenizer:
    """Self-contained BPE tokenizer."""

    def __init__(self, vocab: Optional[Dict[str, int]] = None, merges: Optional[List[Tuple[str, str]]] = None):
        self.special_tokens = ["<pad>", "<unk>", "<bos>", "<eos>"]
        if vocab is not None and merges is not None:
            self.vocab = vocab
            self.inverse_vocab = {v: k for k, v in vocab.items()}
            self.merges = [tuple(m) for m in merges]
        else:
            self.vocab = {tok: idx for idx, tok in enumerate(self.special_tokens)}
            self.inverse_vocab = {idx: tok for tok, idx in self.vocab.items()}
            self.merges = []

    @property
    def vocab_size(self) -> int:
        return len(self.vocab)

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

    def _merge_vocab(self, pair: Tuple[str, str], split_words: Dict[Tuple[str, ...], int]) -> Dict[Tuple[str, ...], int]:
        first, second = pair
        merged = first + second
        new_split_words = {}
        for word, freq in split_words.items():
            new_word = []
            i = 0
            while i < len(word):
                if i < len(word) - 1 and word[i] == first and word[i + 1] == second:
                    new_word.append(merged)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            new_split_words[tuple(new_word)] = freq
        return new_split_words

    def train(self, text: str, target_vocab_size: int = 500, min_freq: int = 2):
        """Train BPE merges on input text up to target_vocab_size."""
        # Initialize with special tokens
        self.vocab = {tok: idx for idx, tok in enumerate(self.special_tokens)}
        self.merges = []

        # Simple pre-tokenization: split on whitespace and punctuation
        words = text.split()
        word_counts = Counter(words)

        # Represent words as tuples of characters with end-of-word marker '</w>'
        split_words = {tuple(list(w) + ["</w>"]): freq for w, freq in word_counts.items()}

        # Seed initial character alphabet
        chars = sorted(list({char for word in split_words for char in word}))
        for char in chars:
            if char not in self.vocab:
                idx = len(self.vocab)
                self.vocab[char] = idx

        # Iteratively find most frequent pair and merge
        num_merges = target_vocab_size - len(self.vocab)
        for _ in range(max(0, num_merges)):
            pairs = self._get_stats(split_words)
            if not pairs:
                break
            best_pair, freq = pairs.most_common(1)[0]
            if freq < min_freq:
                break

            split_words = self._merge_vocab(best_pair, split_words)
            merged_token = best_pair[0] + best_pair[1]
            if merged_token not in self.vocab:
                self.vocab[merged_token] = len(self.vocab)
            self.merges.append(best_pair)

        self.inverse_vocab = {idx: tok for tok, idx in self.vocab.items()}

    def encode(self, text: str, add_special_tokens: bool = False) -> List[int]:
        """Encode text string into list of token IDs."""
        tokens = []
        if add_special_tokens:
            tokens.append(self.bos_id)

        words = text.split()
        for w_idx, word in enumerate(words):
            word_tuple = tuple(list(word) + ["</w>"])
            for pair in self.merges:
                first, second = pair
                merged = first + second
                new_word = []
                i = 0
                while i < len(word_tuple):
                    if i < len(word_tuple) - 1 and word_tuple[i] == first and word_tuple[i + 1] == second:
                        new_word.append(merged)
                        i += 2
                    else:
                        new_word.append(word_tuple[i])
                        i += 1
                word_tuple = tuple(new_word)

            for sym in word_tuple:
                tokens.append(self.vocab.get(sym, self.unk_id))

        if add_special_tokens:
            tokens.append(self.eos_id)

        return tokens

    def decode(self, indices: List[int]) -> str:
        """Decode list of token IDs back into string."""
        tokens = [self.inverse_vocab.get(idx, "") for idx in indices]
        # Remove special tokens
        filtered = [tok for tok in tokens if tok not in self.special_tokens]
        # Reconstruct words from </w> marker
        joined = "".join(filtered).replace("</w>", " ")
        return joined.strip()

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
    def load(cls, filepath: Union[str, Path]) -> "BPETokenizer":
        path = Path(filepath)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(vocab=data["vocab"], merges=data["merges"])
