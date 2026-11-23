"""
Test Suite for Official IMF Client SDK (Track 1).
"""

import threading
import time
from imf.serving_daemon import start_server
from imf.client import IMFClient

def test_imf_client():
    port = 8899
    t = threading.Thread(target=start_server, kwargs={"port": port, "host": "127.0.0.1"}, daemon=True)
    t.start()
    time.sleep(1.0)

    client = IMFClient(base_url=f"http://127.0.0.1:{port}")

    # Test health probe
    h = client.health()
    assert h["status"] == "healthy"
    print("[✓] Client Health Probe:", h)

    # Test standard synchronous chat
    resp = client.chat("Explain Lie SSM", max_tokens=10)
    assert len(resp.text) > 0
    assert resp.manifold_drift > 0.0
    print("[✓] Client Sync Chat Response:", resp)
    print("    Decoded Drift Telemetry:", resp.manifold_drift)
    print("    Decoded Speedup:", resp.speculative_speedup)

    # Test streaming chat
    streamed = []
    for token in client.stream_chat("Stream test", max_tokens=8):
        streamed.append(token)
    full_stream = "".join(streamed)
    assert len(full_stream) > 0
    print("[✓] Client Stream Response:", full_stream.strip())
    print("\n[✓] ALL CLIENT SDK TESTS PASSED!")

if __name__ == "__main__":
    test_imf_client()
