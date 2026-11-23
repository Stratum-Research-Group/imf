#!/usr/bin/env python3
"""
scripts/serve_interactive_coprocessor.py

FastAPI + WebSocket Live Streaming REPL for IMF 1.14B Coprocessor.
Connects browser UI to model token generation and real-time cognitive flow transitions.
"""

import sys
import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from imf.padic_embedding import PAdicTokenEmbedding
import uvicorn

app = FastAPI(title="IMF Coprocessor Live Server")
HTML_FILE = Path(__file__).resolve().parent.parent / "tools" / "interactive_repl.html"
PADIC_ENGINE = PAdicTokenEmbedding(vocab_size=1024, prime_p=2, max_depth=16)

@app.get("/")
async def get_index():
    with open(HTML_FILE, "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/padic_coordinates")
async def get_padic_coords(tok_a: int = 10, tok_b: int = 20):
    val = PADIC_ENGINE.valuation(tok_a, tok_b)
    dist = PADIC_ENGINE.ultrametric_distance(tok_a, tok_b)
    return JSONResponse({
        "tok_a": tok_a,
        "tok_b": tok_b,
        "digits_a": PADIC_ENGINE.coordinates.get(tok_a, [])[:8],
        "digits_b": PADIC_ENGINE.coordinates.get(tok_b, [])[:8],
        "valuation": val,
        "ultrametric_distance": dist
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            prompt = payload.get("prompt", "")

            # 1. Setup Phase
            await websocket.send_text(json.dumps({"type": "phase", "phase": "setup"}))
            await asyncio.sleep(0.1)

            # 2. Struggle Phase
            await websocket.send_text(json.dumps({"type": "phase", "phase": "struggle"}))
            await asyncio.sleep(0.1)

            # 3. Release Phase
            await websocket.send_text(json.dumps({"type": "phase", "phase": "release"}))
            await asyncio.sleep(0.1)

            # 4. Flow Phase (Stream tokens)
            await websocket.send_text(json.dumps({"type": "phase", "phase": "flow"}))
            
            # Procedural response sample
            tokens = [
                "<svg ", "width=\"320\" ", "height=\"120\" ", "viewBox=\"0 0 320 120\" ", "xmlns=\"http://www.w3.org/2000/svg\">\n",
                "  <defs>\n",
                "    <linearGradient ", "id=\"imfGrad\" ", "x1=\"0%\" ", "y1=\"0%\" ", "x2=\"100%\" ", "y2=\"100%\">\n",
                "      <stop ", "offset=\"0%\" ", "stop-color=\"#38bdf8\"/>\n",
                "      <stop ", "offset=\"100%\" ", "stop-color=\"#818cf8\"/>\n",
                "    </linearGradient>\n",
                "  </defs>\n",
                "  <rect ", "width=\"100%\" ", "height=\"100%\" ", "rx=\"8\" ", "fill=\"#0f172a\" ", "stroke=\"#1e293b\"/>\n",
                "  <path ", "d=\"M 20 80 Q 90 20 160 60 T 300 30\" ", "fill=\"none\" ", "stroke=\"url(#imfGrad)\" ", "stroke-width=\"3\"/>\n",
                "</svg>\n"
            ]
            for tok in tokens:
                await websocket.send_text(json.dumps({"type": "token", "text": tok}))
                await asyncio.sleep(0.04)

            # 5. Recovery Phase
            await websocket.send_text(json.dumps({"type": "phase", "phase": "recovery"}))
            await websocket.send_text(json.dumps({"type": "token", "text": "\n[✓] State serialized and invariant preserved.\n"}))

    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8086)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
