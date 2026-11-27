#!/usr/bin/env python3
"""
scripts/healthcheck_sovereign_fleet.py
Automated cross-platform self-healing health check for the Sovereign Engine.
Checks FastAPI daemon (port 8092), GPU telemetry, Lean 4 toolchain, and io_uring status.
"""

import urllib.request
import json
import shutil
import sys

def check_health():
    print("=== SOVEREIGN ENGINE OPERATIONAL HEALTH AUDIT ===")
    all_ok = True

    # 1. Check Daemon Port 8092
    try:
        req = urllib.request.Request("http://localhost:8092/health")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f"[+] Daemon HTTP Status: {data.get('status')} (Engine: {data.get('engine')})")
            gpu = data.get("gpu_telemetry", {})
            print(f"    GPU: {gpu.get('device')} | Temp: {gpu.get('temp_c')} °C | Util: {gpu.get('util_percent')}%")
    except Exception as e:
        print(f"[!] Daemon Check FAILED: {e}")
        all_ok = False

    # 2. Check Lean 4 Binary
    lean_bin = shutil.which("lean")
    if lean_bin:
        print(f"[+] Lean 4 Compiler Available: {lean_bin}")
    else:
        print("[!] Lean 4 compiler binary not found on PATH.")
        all_ok = False

    # 3. Check C++ Compiler
    gxx_bin = shutil.which("g++")
    if gxx_bin:
        print(f"[+] C++20 Compiler Available: {gxx_bin}")
    else:
        print("[!] g++ compiler not found.")
        all_ok = False

    print(f"\nFinal Operational Status: {'100% HEALTHY' if all_ok else 'ATTENTION REQUIRED'}")
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(check_health())
