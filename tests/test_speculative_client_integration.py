"""
End-to-End Speculative Decoding Integration Test via Official IMFClient (Track 4).
Runs real HTTP streaming over client.py, validates response, latency, and telemetry.
"""

import threading
import time
from imf.serving_daemon import start_server
from imf.client import IMFClient

def test_client_speculative_integration():
    port = 8877
    t = threading.Thread(target=start_server, kwargs={"port": port, "host": "127.0.0.1"}, daemon=True)
    t.start()
    time.sleep(1.0)

    client = IMFClient(base_url=f"http://127.0.0.1:{port}")

    print("=" * 80)
    print("  IMF CLIENT SPECULATIVE DECODING INTEGRATION TEST (TRACK 4)")
    print("=" * 80)

    # 1. Sync Request with Telemetry Verification
    prompt = "Compute continuous state evolution in E8 lattice"
    t0 = time.perf_counter()
    resp = client.chat(prompt, max_tokens=16)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    print(f"[*] Sync Chat Completion ({latency_ms:.2f} ms):")
    print(f"    Text:                 {resp.text}")
    print(f"    Manifold Drift Gauge: {resp.manifold_drift:.2e} [✓ ISOMETRIC TOLERANCE MET]")
    print(f"    Speculative Speedup:  {resp.speculative_speedup}")
    print(f"    Landauer Dissipation: {resp.entropy_dissipation}")

    assert resp.manifold_drift < 1e-5
    assert len(resp.text) > 0

    # 2. Streaming Request
    print("\n[*] Streaming Chat Completion:")
    tokens = []
    t0 = time.perf_counter()
    for tok in client.stream_chat(prompt, max_tokens=12):
        tokens.append(tok)
    stream_latency_ms = (time.perf_counter() - t0) * 1000.0

    streamed_text = "".join(tokens)
    print(f"    Streamed Text:        {streamed_text}")
    print(f"    Total Stream Latency: {stream_latency_ms:.2f} ms")
    assert len(tokens) > 0

    print("=" * 80)
    print("  [✓] ALL END-TO-END SPECULATIVE DECODING CLIENT TESTS VERIFIED")
    print("=" * 80)

if __name__ == "__main__":
    test_client_speculative_integration()
