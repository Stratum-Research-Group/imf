"""
Official Python Client SDK for IMF Serving Engine (Track 1).
Provides synchronous and asynchronous clients with streaming, WebSockets,
and automatic Lie-group manifold drift telemetry decoding.
"""

import json
import urllib.request
import urllib.error
from typing import Generator, Dict, Any, Optional

class IMFResponse:
    def __init__(self, data: Dict[str, Any], headers: Dict[str, str]):
        self.data = data
        self.headers = headers
        self.text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        self.manifold_drift = float(headers.get("x-imf-manifold-drift", headers.get("X-IMF-Manifold-Drift", "0.0")))
        self.speculative_speedup = headers.get("x-imf-speculative-speedup", headers.get("X-IMF-Speculative-Speedup", "1.0x"))
        self.entropy_dissipation = headers.get("x-imf-entropy-dissipation", headers.get("X-IMF-Entropy-Dissipation", "0.0 nJ"))

    def __repr__(self) -> str:
        return f"<IMFResponse text='{self.text[:30]}...' drift={self.manifold_drift} speedup={self.speculative_speedup}>"

class IMFClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def health(self) -> Dict[str, Any]:
        url = f"{self.base_url}/healthz"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def chat(self, prompt: str, max_tokens: int = 32, model: Optional[str] = None) -> IMFResponse:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model or "imf-century-70b-polytope",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": False
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            headers = {k: v for k, v in resp.headers.items()}
            return IMFResponse(body, headers)

    def stream_chat(self, prompt: str, max_tokens: int = 32) -> Generator[str, None, None]:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": "imf-century-70b-polytope",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": True
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            for line in resp:
                line_str = line.decode("utf-8").strip()
                if not line_str or line_str == "data: [DONE]":
                    continue
                if line_str.startswith("data: "):
                    chunk = json.loads(line_str[6:])
                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if delta:
                        yield delta
