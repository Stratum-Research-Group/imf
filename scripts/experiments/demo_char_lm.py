"""
demo_char_lm.py
Self-contained character-level language modeling demonstration with IMF.
Trains an IMFLanguageModel on an embedded snippet of Shakespeare and generates
text autoregressively using O(1) streaming decoding state.
Zero external dependencies required.
"""

import time
import torch
import torch.nn.functional as F
from pretrain_imf_lm import IMFLanguageModel

CORPUS = """
First Citizen:
Before we proceed any further, hear me speak.

All:
Speak, speak.

First Citizen:
You are all resolved rather to die than to famish?

All:
Resolved. resolved.

First Citizen:
First, you know Caius Marcius is chief enemy to the people.

All:
We know't, we know't.

First Citizen:
Let us kill him, and we'll have corn at our own price.
Is't a verdict?

All:
No more talking on't; let it be done: away, away!

Second Citizen:
One word, good citizens.

First Citizen:
We are accounted poor citizens, the patricians good.
What authority surfeits on would relieve us: if they
would yield us but the superfluity, while it were
wholesome, we might guess they relieved us humanely;
but they think we are too dear.
"""

class CharTokenizer:
    """Zero-dependency character tokenizer."""
    def __init__(self, text: str):
        chars = sorted(list(set(text)))
        self.char2idx = {ch: i for i, ch in enumerate(chars)}
        self.idx2char = {i: ch for i, ch in enumerate(chars)}
        self.vocab_size = len(chars)

    def encode(self, text: str) -> list[int]:
        return [self.char2idx[c] for c in text]

    def decode(self, indices: list[int]) -> str:
        return "".join([self.idx2char.get(i, "?") for i in indices])


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 75)
    print(f"IMF CHARACTER-LEVEL LANGUAGE MODEL DEMO on {device}")
    print("=" * 75)

    tokenizer = CharTokenizer(CORPUS)
    print(f"[*] Character Vocabulary Size: {tokenizer.vocab_size} unique symbols")

    # Encode full dataset
    data = torch.tensor(tokenizer.encode(CORPUS), dtype=torch.long, device=device)
    seq_len = 64
    d_model = 64
    n_layers = 2
    batch_size = 4

    model = IMFLanguageModel(
        vocab_size=tokenizer.vocab_size,
        d_model=d_model,
        n_layers=n_layers,
        preset="decayotton_orthoplex"
    ).to(device)

    opt = torch.optim.AdamW(model.parameters(), lr=0.005, weight_decay=0.01)

    print(f"[*] Training IMF Language Model ({sum(p.numel() for p in model.parameters()):,} parameters)...")
    model.train()
    num_steps = 100
    t0 = time.perf_counter()

    for step in range(1, num_steps + 1):
        # Sample random chunk
        idx = torch.randint(0, len(data) - seq_len - 1, (batch_size,))
        x = torch.stack([data[i:i + seq_len] for i in idx])
        y = torch.stack([data[i + 1:i + seq_len + 1] for i in idx])

        opt.zero_grad()
        logits = model(x)
        loss = F.cross_entropy(logits.view(-1, tokenizer.vocab_size), y.view(-1))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

        if step % 25 == 0 or step == 1:
            print(f"  Step {step:3d}/{num_steps} | Loss: {loss.item():.4f}")

    total_time = (time.perf_counter() - t0) * 1000
    print(f"[+] Training complete in {total_time:.1f} ms ({total_time / num_steps:.2f} ms/step)")

    # Autoregressive O(1) Streaming Generation
    print("\n[*] Testing O(1) Streaming Generation from Prompt:")
    model.eval()
    prompt = "First Citizen:"
    print(f"  Prompt: '{prompt}'")
    prompt_ids = tokenizer.encode(prompt)

    states = model.init_streaming_states(batch_size=1, device=device)

    # Ingest prompt into recurrent state
    with torch.no_grad():
        for ch_idx in prompt_ids[:-1]:
            tok = torch.tensor([ch_idx], device=device)
            _, states = model.generate_step(tok, states)

        curr_tok = torch.tensor([prompt_ids[-1]], device=device)
        generated = list(prompt_ids)

        for _ in range(80):
            logits, states = model.generate_step(curr_tok, states)
            probs = F.softmax(logits / 0.8, dim=-1) # Temperature 0.8
            next_tok = torch.multinomial(probs, num_samples=1).squeeze(0)
            generated.append(next_tok.item())
            curr_tok = next_tok

    decoded = tokenizer.decode(generated)
    print("\n[Generated Continuation]:")
    print("-" * 50)
    print(decoded)
    print("-" * 50)
    print("=" * 75)


if __name__ == "__main__":
    main()
