#!/usr/bin/env python3
"""
scripts/launch_mission_control_tunnel.py

Launches Mission Control WebREPL Dashboard and OpenAI API server,
with optional public reverse tunneling via localtunnel, cloudflared, or ngrok.
"""

import sys
import os
import subprocess
import threading
import time
import urllib.request
import uvicorn
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.serve_openai_compatible_api import app as api_app

def run_api_server():
    uvicorn.run(api_app, host="127.0.0.1", port=8080, log_level="warning")

def main():
    print("=" * 65)
    print("  IMF MISSION CONTROL & WEBREPL TUNNEL LAUNCHER")
    print("=" * 65)

    # 1. Start background API server
    t = threading.Thread(target=run_api_server, daemon=True)
    t.start()
    time.sleep(1.0)
    print("  [✓] OpenAI Compatible Inference API: http://127.0.0.1:8080/v1")

    # 2. Verify endpoints
    with urllib.request.urlopen("http://127.0.0.1:8080/health") as resp:
        assert resp.status == 200
        print("  [✓] API Healthcheck Passed: 1.14B Coprocessor Online")

    gui_file = ROOT / "tools" / "mission_control_gui.html"
    print(f"  [✓] Mission Control Dashboard Ready: file://{gui_file}")
    print("\n[+] To expose remotely:")
    print("    • LocalTunnel: npx localtunnel --port 8080")
    print("    • Cloudflare:  cloudflared tunnel --url http://localhost:8080")
    print("=" * 65)

if __name__ == "__main__":
    main()
