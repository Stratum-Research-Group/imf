"""
imf/ws_proof_bridge.py
Real-time WebSocket Lean 4 Proof Bridge.
Listens for user conjectures and natural problem prompts from the Mission Control WebUI,
auto-formalizes them through the LeanAutoFormalizer engine, verifies zero-axiom certification
in Lean 4 Core, and streams live verification metrics and proof AST back to the dashboard.
"""

import asyncio
import json
import time
from typing import Dict, Any
import websockets
from imf.lean_autoformalizer import LeanAutoFormalizer

autoformalizer = LeanAutoFormalizer()

async def handle_client(websocket):
    print(f"[*] Dashboard client connected: {websocket.remote_address}")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type", "formalize")

                if msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong", "timestamp": time.time()}))
                    continue

                if msg_type == "formalize":
                    problem_text = data.get("problem", "Prove that n + m = m + n for natural numbers.")
                    problem_id = data.get("id", f"user_query_{int(time.time())}")

                    # Notify client: formalization started
                    await websocket.send(json.dumps({
                        "type": "status",
                        "status": "formalizing",
                        "problem_id": problem_id
                    }))

                    # Run autoformalization in thread pool to not block asyncio event loop
                    loop = asyncio.get_running_loop()
                    res = await loop.run_in_executor(
                        None, autoformalizer.formalize_and_prove, problem_text, problem_id
                    )

                    # Send verified result
                    await websocket.send(json.dumps({
                        "type": "proof_result",
                        "result": res
                    }))
                    print(f"[✓] Processed conjecture '{problem_id}': verified={res['verified']} in {res['latency_ms']:.1f}ms")

            except Exception as e:
                await websocket.send(json.dumps({
                    "type": "error",
                    "error": str(e)
                }))
    except websockets.exceptions.ConnectionClosed:
        print(f"[-] Dashboard client disconnected: {websocket.remote_address}")


async def main():
    port = 8766
    host = "127.0.0.1"
    print("=" * 80)
    print(f"  IMF LEAN 4 INTERACTIVE PROOF WEBSOCKET BRIDGE")
    print(f"  Listening on ws://{host}:{port}")
    print("=" * 80)
    async with websockets.serve(handle_client, host, port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
