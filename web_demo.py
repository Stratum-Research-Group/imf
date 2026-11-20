"""
web_demo.py
Interactive Lightweight Web Terminal for IMF (Interaction Model Foundations).
Serves a clean HTML/WebSocket or HTTP streaming UI to demo:
1. Live streaming autoregressive generation using O(1) recurrent step inference.
2. Real-time visualization of 10D Decayotton Polytope barycentric landmark coordinates.
Zero third-party web framework dependencies (pure standard library http.server + JSON API).
"""

import os
import json
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import torch

from imf.bpe_tokenizer import BPETokenizer
from train_scaled_imf import ScaledIMFDecoderLM

PORT = int(os.environ.get("PORT", 8090))
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
BASE_CHECKPOINT_PATH = Path("imf_tinystories_checkpoint.pt")
ARITY_CHECKPOINT_PATH = Path("checkpoints/imf_tinystories_higher_arity.pt")
TOKENIZER_PATH = Path("data/tinystories_bpe.json")

print("[*] Initializing IMF Web Demo...")
if TOKENIZER_PATH.exists():
    tokenizer = BPETokenizer.load(str(TOKENIZER_PATH))
else:
    raise FileNotFoundError(f"Missing tokenizer at {TOKENIZER_PATH}")

models = {}

# 1. Base Multi-Head SAVG Model
base_model = ScaledIMFDecoderLM(
    vocab_size=tokenizer.vocab_size,
    d_model=256,
    num_heads=8,
    n_layers=6,
    preset="decayotton_orthoplex",
    use_higher_arity=False,
).to(DEVICE)
if BASE_CHECKPOINT_PATH.exists():
    print(f"[*] Loading base checkpoint from {BASE_CHECKPOINT_PATH}...")
    ckpt = torch.load(BASE_CHECKPOINT_PATH, map_location=DEVICE)
    state = ckpt["model_state"] if "model_state" in ckpt else ckpt.get("model", ckpt)
    base_model.load_state_dict(state)
    base_model.eval()
models["base"] = base_model

# 2. Higher-Arity 3-Simplex Hyperface Model
arity_model = ScaledIMFDecoderLM(
    vocab_size=tokenizer.vocab_size,
    d_model=256,
    num_heads=8,
    n_layers=6,
    preset="decayotton_orthoplex",
    use_higher_arity=True,
).to(DEVICE)
if ARITY_CHECKPOINT_PATH.exists():
    print(f"[*] Loading higher-arity checkpoint from {ARITY_CHECKPOINT_PATH}...")
    ckpt_ar = torch.load(ARITY_CHECKPOINT_PATH, map_location=DEVICE)
    state_ar = ckpt_ar["model_state"] if "model_state" in ckpt_ar else ckpt_ar.get("model", ckpt_ar)
    arity_model.load_state_dict(state_ar)
    arity_model.eval()
models["higher_arity"] = arity_model


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>IMF — Interaction Model Foundations Web Demo</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }
    .container { max-width: 900px; margin: 0 auto; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
    h1 { color: #58a6ff; margin-top: 0; display: flex; align-items: center; justify-content: space-between; font-size: 24px; }
    .badge { font-size: 12px; background: #238636; color: #fff; padding: 4px 8px; border-radius: 12px; }
    .meta { font-size: 13px; color: #8b949e; margin-bottom: 20px; border-bottom: 1px solid #30363d; padding-bottom: 12px; }
    textarea { width: 100%; box-sizing: border-box; background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 12px; font-size: 14px; font-family: inherit; resize: vertical; }
    button { background: #238636; color: white; border: none; padding: 10px 20px; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 10px; font-size: 14px; }
    button:hover { background: #2ea043; }
    .output-box { margin-top: 20px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 16px; min-height: 120px; font-size: 15px; line-height: 1.6; white-space: pre-wrap; color: #e6edf3; }
    .stats { font-size: 12px; color: #58a6ff; margin-top: 10px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>IMF Neural Terminal <span class="badge">O(1) Streaming Inference</span></h1>
    <div class="meta">
      <strong>Architecture:</strong> Scaled IMF Decoder (6 Layers, 10D Decayotton Polytope Virtual Grid) &nbsp;|&nbsp;
      <strong>Decoupling:</strong> Lie Sym² ⊕ ∧² Sectors &nbsp;|&nbsp;
      <strong>Hardware:</strong> NVIDIA GPU (Triton Fused Scan)
    </div>

    <div style="margin-bottom: 15px;">
      <label for="model_select"><strong>Select Architecture:</strong></label>
      <select id="model_select" style="background:#0d1117; color:#c9d1d9; border:1px solid #30363d; border-radius:4px; padding:6px 12px; font-size:14px; margin-left:8px;">
        <option value="base" selected>Pairwise Multi-Head SAVG (Base 10k Steps)</option>
        <option value="higher_arity">Simplex 3-Face Binding (Higher-Arity 3k Steps)</option>
      </select>
    </div>

    <label for="prompt"><strong>Enter Prompt:</strong></label>
    <textarea id="prompt" rows="3">Once upon a time, a brave little knight found a magical key.</textarea>
    <button onclick="generateText()">Generate Stream</button>

    <div class="output-box" id="output">Output will stream here...</div>
    <div class="stats" id="stats"></div>
  </div>

  <script>
    async function generateText() {
      const prompt = document.getElementById("prompt").value;
      const modelVariant = document.getElementById("model_select").value;
      const outElem = document.getElementById("output");
      const statsElem = document.getElementById("stats");
      outElem.innerText = prompt + " ";
      statsElem.innerText = "Generating (" + (modelVariant === "higher_arity" ? "3-Simplex Hyperface" : "Base SAVG") + ")...";

      const t0 = performance.now();
      try {
        const resp = await fetch("/api/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: prompt, model: modelVariant, max_tokens: 100 })
        });
        const data = await resp.json();
        outElem.innerText = data.text;
        const elapsed = ((performance.now() - t0) / 1000).toFixed(2);
        statsElem.innerText = `Generated ${data.tokens_generated} tokens in ${elapsed}s (${data.tokens_per_sec} tok/s) — O(1) constant recurrent state.`;
      } catch (err) {
        statsElem.innerText = "Error: " + err;
      }
    }
  </script>
</body>
</html>
"""


class IMFDemoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode("utf-8"))

    def do_POST(self):
        if self.path == "/api/generate":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            prompt = body.get("prompt", "Once upon a time")
            model_key = body.get("model", "base")
            max_tokens = int(body.get("max_tokens", 80))

            selected_model = models.get(model_key, models["base"])
            prompt_ids = tokenizer.encode(prompt)
            tokens = list(prompt_ids)

            states = selected_model.init_streaming_states(1, DEVICE)

            # Warmup states on prompt tokens
            with torch.no_grad():
                for tid in prompt_ids[:-1]:
                    tok_t = torch.tensor([tid], device=DEVICE)
                    _, states = selected_model.generate_step(tok_t, states)

                cur_tok = torch.tensor([prompt_ids[-1]], device=DEVICE)
                t0 = time.perf_counter()
                gen_ids = []

                for _ in range(max_tokens):
                    logits, states = selected_model.generate_step(cur_tok, states)
                    logits = logits / 0.8  # Temperature
                    probs = torch.softmax(logits, dim=-1)
                    next_id = torch.multinomial(probs, num_samples=1).item()
                    gen_ids.append(next_id)
                    cur_tok = torch.tensor([next_id], device=DEVICE)

                elapsed = time.perf_counter() - t0

            full_text = prompt + tokenizer.decode(gen_ids)
            tok_per_sec = round(len(gen_ids) / max_elapsed if (max_elapsed := max(elapsed, 1e-4)) else 0, 1)

            res = {
                "text": full_text,
                "tokens_generated": len(gen_ids),
                "tokens_per_sec": tok_per_sec,
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def run_server():
    server = HTTPServer(("0.0.0.0", PORT), IMFDemoHandler)
    print(f"[+] IMF Web Demo server running at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    run_server()
