"""
imf/telemetry_ws.py
Lightweight WebSocket daemon streaming real-time telemetry from
the POSIX zero-copy shared memory ring (/dev/shm/imf_shm_ring)
to web frontends and the 3D Polytope Visualizer (dist/polytope_viewer.html).
"""

import asyncio
import json
import os
import struct
import websockets
from pathlib import Path

SHM_PATH = "/dev/shm/imf_shm_ring"


def read_shm_telemetry() -> dict:
    """Reads telemetry record from POSIX shared memory ring."""
    if not os.path.exists(SHM_PATH):
        # Fallback simulated data if SHM is not yet populated
        return {
            "magic": "IMF_SHM_V1",
            "sequence_id": 0,
            "timestamp_ns": 0,
            "manifold_drift": 1.82e-6,
            "speculative_speedup": 4.72,
            "tokens_per_sec": 843891.0,
            "status": "FALLBACK"
        }

    try:
        with open(SHM_PATH, "rb") as f:
            header_size = 24  # struct.calcsize("<4sIIffI") = 4 + 4 + 4 + 4 + 4 + 4 = 24
            data = f.read(header_size)
            if len(data) < header_size:
                return {"status": "INCOMPLETE"}
            magic, head, tail, drift, speedup, flags = struct.unpack("<4sIIffI", data)
            return {
                "magic": magic.decode("ascii", errors="ignore").strip("\x00"),
                "head": head,
                "tail": tail,
                "manifold_drift": drift,
                "speculative_speedup": speedup,
                "flags": flags,
                "status": "LIVE"
            }
    except Exception as e:
        return {"error": str(e), "status": "ERROR"}


async def telemetry_handler(websocket):
    """Streams JSON telemetry updates every 100ms over WebSocket."""
    while True:
        try:
            telemetry = read_shm_telemetry()
            await websocket.send(json.dumps(telemetry))
            await asyncio.sleep(0.1)
        except websockets.exceptions.ConnectionClosed:
            break
        except Exception:
            await asyncio.sleep(0.5)


async def main():
    port = int(os.environ.get("IMF_WS_PORT", 8765))
    host = os.environ.get("IMF_WS_HOST", "127.0.0.1")
    print(f"[*] Starting IMF Telemetry WebSocket Bridge on ws://{host}:{port}...")
    async with websockets.serve(telemetry_handler, host, port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Telemetry bridge shut down.")
