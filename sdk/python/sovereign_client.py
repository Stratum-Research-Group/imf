"""
sdk/python/sovereign_client.py
Zero-dependency, type-safe Python client library for connecting to the
local Sovereign API Daemon and streaming continuous Lie-algebraic token flows.
"""

import urllib.request
import json
import time
from typing import Generator, Dict, Any, List

class SovereignClient:
    """
    Client for interacting with the local Sovereign Inference Engine.
    Defaults to endpoint: http://localhost:8092 (Sovereign API Port)
    """
    def __init__(self, base_url: str = "http://localhost:8092"):
        self.base_url = base_url.rstrip("/")

    def health(self) -> Dict[str, Any]:
        """Checks daemon availability and hardware status."""
        req = urllib.request.Request(f"{self.base_url}/health")
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            return {"status": "offline", "error": str(e)}

    def complete(self, prompt: str, max_tokens: int = 128, temperature: float = 0.7) -> Dict[str, Any]:
        """Executes non-streaming completion."""
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            return json.loads(resp.read().decode('utf-8'))

if __name__ == '__main__':
    client = SovereignClient()
    print("Testing Sovereign Client connection to daemon on port 8092...")
    status = client.health()
    print("Health Status:", status.get('status', 'offline'))
    print("Engine:", status.get('engine', 'unknown'))
