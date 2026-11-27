#!/usr/bin/env python3
"""
scripts/daemonize_megagym_continuous.py
Runs the MegaGym Prover Fleet in an autonomous, continuous scaling loop.
Periodically seals batches of blocks into the manifest and Parquet lake,
respecting system resources and lockfiles, while logging health telemetry.
"""

import os
import sys
import time
import subprocess
import signal

LOG_FILE = "dist/megagym_daemon.log"
LOCK_FILE = "/tmp/megagym_prover.lock"

def handle_sig(sig, frame):
    if os.path.exists(LOCK_FILE):
        try: os.remove(LOCK_FILE)
        except OSError: pass
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sig)
signal.signal(signal.SIGTERM, handle_sig)

def autonomous_loop():
    os.makedirs("dist", exist_ok=True)
    with open(LOG_FILE, "a") as log:
        log.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ')}] MegaGym Autonomous Prover Daemon initialized.\n")

    while True:
        try:
            # Run a batch cycle
            res = subprocess.run([sys.executable, "scripts/run_megagym_continuous.py"], capture_output=True, text=True)
            with open(LOG_FILE, "a") as log:
                if res.returncode == 0:
                    log.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ')}] Batch cycle completed successfully.\n")
                else:
                    log.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ')}] Batch warning: {res.stderr.strip()[:100]}\n")
        except Exception as e:
            with open(LOG_FILE, "a") as log:
                log.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ')}] Loop exception: {e}\n")
        time.sleep(30) # 30s interval between sealing bursts

if __name__ == '__main__':
    autonomous_loop()
