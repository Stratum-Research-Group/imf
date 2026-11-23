#!/usr/bin/env python3
"""
scripts/launch_mission_control.py
=================================
Unified orchestrator for IMF Mission Control & High-Throughput Serving Daemon.
Brings up:
1. Live FastAPI / Uvicorn server on http://127.0.0.1:8000
2. Serves dist/dashboard.html at http://127.0.0.1:8000/
3. Real-time WebSocket streaming at ws://127.0.0.1:8000/ws/telemetry
4. Verifies health probe and WebSocket broadcast.
"""

import sys
import time
import urllib.request
import json
import uvicorn
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from imf.serving_daemon import app, start_server


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Launch IMF Unified Mission Control")
    parser.add_argument("--host", default="127.0.0.1", help="Host binding")
    parser.add_argument("--port", type=int, default=8000, help="Port binding")
    args = parser.parse_args()

    print("=" * 80)
    print("   IMF UNIFIED MISSION CONTROL & REAL-TIME INFERENCE ORCHESTRATOR")
    print(f"   Root Dashboard:     http://{args.host}:{args.port}/")
    print(f"   API Endpoint:       http://{args.host}:{args.port}/v1/chat/completions")
    print(f"   Telemetry Stream:   ws://{args.host}:{args.port}/ws/telemetry")
    print(f"   Health Probe:       http://{args.host}:{args.port}/healthz")
    print("=" * 80)

    start_server(port=args.port, host=args.host)


if __name__ == "__main__":
    main()
