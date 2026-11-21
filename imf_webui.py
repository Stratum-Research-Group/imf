"""
IMF Interactive WebUI & Live Manifold Playground Server.
FastAPI backend serving real-time Polytope activation visualization,
fused speculative decoding benchmark, and Lean 4 formal proof editor.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import time
from typing import Dict, Any, Optional
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from imf.coprocessor_bridge import IMFCoprocessorBridge

app = FastAPI(title="IMF Interactive Polytope & Formal Reasoning Playground")
bridge = None


def get_bridge():
    global bridge
    if bridge is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        bridge = IMFCoprocessorBridge(device=device)
    return bridge


class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 32
    temperature: float = 0.0


class VerifyLeanRequest(BaseModel):
    code: str


class VerifyPythonRequest(BaseModel):
    code: str
    expected_output: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>IMF Interactive Polytope & Reasoning Playground</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { background-color: #0b0f19; color: #e2e8f0; font-family: ui-sans-serif, system-ui, sans-serif; }
    .card { background-color: #131b2e; border: 1px solid #1e293b; border-radius: 10px; }
  </style>
</head>
<body class="p-8 max-w-6xl mx-auto">
  <header class="mb-8 border-b border-slate-800 pb-4">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-300">
          IMF Interactive Manifold Playground
        </h1>
        <p class="text-slate-400 mt-1">129.8M Joint-Recon Model &bull; Fused Polytope Speculative Decoding &bull; Lean 4 Core Gates</p>
      </div>
      <div class="bg-indigo-950 border border-indigo-700 px-4 py-2 rounded-lg text-xs font-mono text-indigo-300">
        Engine: 102 tok/s &bull; RTX 5060 Ti &bull; CUDA 13.5
      </div>
    </div>
  </header>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <!-- Left: Speculative Generation -->
    <div class="card p-6">
      <h2 class="text-xl font-bold mb-4 text-blue-400 flex items-center gap-2">
        <span>⚡</span> Speculative Polytope Decoder (102 tok/s)
      </h2>
      <label class="block text-xs uppercase text-slate-400 font-semibold mb-2">Prompt:</label>
      <textarea id="promptInput" rows="3" class="w-full bg-slate-900 border border-slate-700 rounded p-3 text-sm font-mono focus:outline-none focus:border-blue-500">def quicksort(arr):</textarea>
      
      <div class="mt-4 flex gap-4">
        <button onclick="runSpeculative()" class="bg-blue-600 hover:bg-blue-500 text-white font-medium px-5 py-2 rounded transition">
          Generate Speculative
        </button>
      </div>

      <div class="mt-6">
        <label class="block text-xs uppercase text-slate-400 font-semibold mb-2">Metrics & Throughput:</label>
        <div id="genMetrics" class="text-xs font-mono text-emerald-400 bg-slate-950 p-3 rounded border border-slate-800">
          Ready for generation...
        </div>
        <label class="block text-xs uppercase text-slate-400 font-semibold mt-4 mb-2">Output Completion:</label>
        <pre id="genOutput" class="bg-slate-950 p-3 rounded border border-slate-800 text-sm font-mono whitespace-pre-wrap text-slate-200">Completion appears here...</pre>
      </div>
    </div>

    <!-- Right: Formal Logic & Code Verifier -->
    <div class="card p-6">
      <h2 class="text-xl font-bold mb-4 text-indigo-400 flex items-center gap-2">
        <span>🛡️</span> Lean 4 & Python Verification Oracle
      </h2>
      <div class="flex gap-2 mb-3">
        <button onclick="setTab('lean')" id="tabLean" class="bg-indigo-600 text-xs px-3 py-1.5 rounded font-semibold text-white">Lean 4 Formal Proof</button>
        <button onclick="setTab('py')" id="tabPy" class="bg-slate-800 text-xs px-3 py-1.5 rounded font-semibold text-slate-400">Python Sandbox</button>
      </div>

      <textarea id="verifyInput" rows="7" class="w-full bg-slate-900 border border-slate-700 rounded p-3 text-sm font-mono focus:outline-none focus:border-indigo-500">theorem add_zero (n : Nat) : n + 0 = n := by rfl</textarea>

      <div class="mt-4">
        <button onclick="runVerify()" class="bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-5 py-2 rounded transition">
          Verify via Ground Truth
        </button>
      </div>

      <div class="mt-6">
        <label class="block text-xs uppercase text-slate-400 font-semibold mb-2">Verification Verdict:</label>
        <div id="verifyResult" class="bg-slate-950 p-3 rounded border border-slate-800 text-xs font-mono text-slate-300">
          Status: Awaiting input...
        </div>
      </div>
    </div>
  </div>

  <script>
    let activeTab = 'lean';
    function setTab(tab) {
      activeTab = tab;
      if (tab === 'lean') {
        document.getElementById('tabLean').className = 'bg-indigo-600 text-xs px-3 py-1.5 rounded font-semibold text-white';
        document.getElementById('tabPy').className = 'bg-slate-800 text-xs px-3 py-1.5 rounded font-semibold text-slate-400';
        document.getElementById('verifyInput').value = 'theorem add_zero (n : Nat) : n + 0 = n := by rfl';
      } else {
        document.getElementById('tabPy').className = 'bg-indigo-600 text-xs px-3 py-1.5 rounded font-semibold text-white';
        document.getElementById('tabLean').className = 'bg-slate-800 text-xs px-3 py-1.5 rounded font-semibold text-slate-400';
        document.getElementById('verifyInput').value = 'def factorial(n):\\n    return 1 if n <= 1 else n * factorial(n - 1)\\nprint(factorial(5))';
      }
    }

    async function runSpeculative() {
      const prompt = document.getElementById('promptInput').value;
      document.getElementById('genMetrics').innerText = 'Generating via Fused Speculative Polytope Decoder (gamma=4)...';
      try {
        const res = await fetch('/api/generate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({prompt: prompt, max_tokens: 40})
        });
        const data = await res.json();
        document.getElementById('genMetrics').innerText = `Throughput: ${data.throughput_tok_s} tok/s | Acceptance Rate: ${data.acceptance_rate}% | Latency: ${data.duration_ms} ms`;
        document.getElementById('genOutput').innerText = data.completion;
      } catch (e) {
        document.getElementById('genMetrics').innerText = 'Error: ' + e;
      }
    }

    async function runVerify() {
      const code = document.getElementById('verifyInput').value;
      const endpoint = activeTab === 'lean' ? '/api/verify/lean' : '/api/verify/python';
      document.getElementById('verifyResult').innerText = 'Running verification compiler...';
      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({code: code})
        });
        const data = await res.json();
        const badge = data.verified ? '✅ PASSED (Verified Ground Truth)' : '❌ FAILED';
        document.getElementById('verifyResult').innerHTML = `<strong>${badge}</strong>\\nLatency: ${data.duration_ms} ms\\nStdout: ${data.stdout || '(none)'}\\nStderr: ${data.stderr || '(none)'}`;
      } catch (e) {
        document.getElementById('verifyResult').innerText = 'Error: ' + e;
      }
    }
  </script>
</body>
</html>
"""


@app.post("/api/generate")
def api_generate(req: GenerateRequest):
    b = get_bridge()
    return b.generate_speculative(prompt=req.prompt, max_tokens=req.max_tokens)


@app.post("/api/verify/lean")
def api_verify_lean(req: VerifyLeanRequest):
    b = get_bridge()
    return b.verify_lean4_code(req.code)


@app.post("/api/verify/python")
def api_verify_python(req: VerifyPythonRequest):
    b = get_bridge()
    return b.verify_python_execution(req.code, expected_output=req.expected_output)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
