"""
imf/test_telemetry_client.py
Real-Time Telemetry Client Smoke Test & Performance Validator.
Connects to ws://127.0.0.1:8765, validates packet structure,
computes end-to-end network latency, and asserts Landauer manifold drift bounds.
"""

import asyncio
import json
import time
import websockets

async def validate_telemetry_stream(num_packets: int = 5):
    print("=" * 80)
    print("  IMF REAL-TIME TELEMETRY WEBSOCKET CLIENT VALIDATOR")
    print("  Connecting to ws://127.0.0.1:8765...")
    print("=" * 80)

    uri = "ws://127.0.0.1:8765"
    async with websockets.connect(uri) as ws:
        latencies = []
        for i in range(num_packets):
            t0 = time.perf_counter()
            msg = await ws.recv()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed_ms)

            data = json.loads(msg)
            print(f"  [Packet {i+1:02d}] Step: {data.get('step')} | Drift: {data.get('manifold_drift'):.2e} | Latency: {elapsed_ms:5.2f} ms")
            print(f"    Poincaré Coords: {data.get('token_poincare_coords')} | Active Experts: {data.get('active_experts')}")

            # Assert invariants
            assert abs(data.get("manifold_drift", 0)) < 1e-4, "Manifold drift exceeded threshold!"
            assert data.get("norm_conservation") == 1.0, "Norm conservation violated!"

    avg_lat = sum(latencies) / len(latencies)
    print("=" * 80)
    print(f"[✓] Telemetry Stream Verified: {num_packets} Packets Validated.")
    print(f"    Mean Packet Receive Latency: {avg_lat:.2f} ms")
    print(f"    All Invariants Passed: Bounded Manifold Drift & Symplectic Norm Conservation")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(validate_telemetry_stream(5))
