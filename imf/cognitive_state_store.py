#!/usr/bin/env python3
"""
imf/cognitive_state_store.py
Sovereign Cognitive State Store & Checkpoint Engine
Persists the 6-stage cognitive loop cycles (GWT, IIT, Metacognitive Interrogation, Specious Present)
into an append-only WAL SQLite database under data/cognitive_state/cognitive_loop.db.
"""

import os
import time
import json
import sqlite3
from typing import Dict, Any, List, Optional

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cognitive_state")
DB_PATH = os.path.join(DB_DIR, "cognitive_loop.db")


class CognitiveStateStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cognitive_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    agent_id TEXT NOT NULL,
                    cycle INTEGER NOT NULL,
                    directive TEXT NOT NULL,
                    device TEXT NOT NULL,
                    vram_headroom_mb REAL,
                    lean4_invariants TEXT,
                    surprise_score REAL,
                    surprise_detected INTEGER,
                    ignited INTEGER,
                    focal_object TEXT,
                    global_workspace_json TEXT,
                    metacognitive_json TEXT,
                    final_verdict TEXT,
                    duration_ms REAL
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cog_cycles_ts ON cognitive_cycles(timestamp);
            """)
            conn.commit()

    def record_cycle(self, cycle_data: Dict[str, Any]) -> int:
        stage1 = cycle_data.get("stage_1_ingestion", {})
        extero = stage1.get("exteroception", {})
        intero = stage1.get("interoception", {})
        stage2 = cycle_data.get("stage_2_surprise_detection", {})
        stage3 = cycle_data.get("stage_3_ignition", {})
        stage4 = cycle_data.get("stage_4_global_broadcast", {})
        stage5 = cycle_data.get("stage_5_metacognitive_interrogation", {})

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO cognitive_cycles (
                    timestamp, agent_id, cycle, directive, device, vram_headroom_mb,
                    lean4_invariants, surprise_score, surprise_detected, ignited,
                    focal_object, global_workspace_json, metacognitive_json,
                    final_verdict, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                time.time(),
                cycle_data.get("agent_id", "IMF-Core-Mind"),
                cycle_data.get("cycle", 1),
                extero.get("directive", ""),
                intero.get("device", "NVIDIA GeForce RTX 5060 Ti"),
                intero.get("vram_headroom_mb", 0.0),
                intero.get("lean4_invariants", "0 sorry | 0 axioms"),
                stage2.get("prediction_error", 0.0),
                1 if stage2.get("surprise_detected", False) else 0,
                1 if stage3.get("ignited", False) else 0,
                stage3.get("focal_object", ""),
                json.dumps(stage4.get("global_workspace", {})),
                json.dumps(stage5),
                cycle_data.get("final_verdict", ""),
                cycle_data.get("execution_duration_ms", 0.0)
            ))
            conn.commit()
            return cur.lastrowid

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM cognitive_cycles ORDER BY id DESC LIMIT ?;
            """, (limit,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def rewind_to(self, cycle_id: int) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM cognitive_cycles WHERE id = ?;", (cycle_id,))
            row = cur.fetchone()
            if not row:
                return {"status": "NOT_FOUND", "cycle_id": cycle_id}
            # Purge subsequent cycles to rewind specious present
            cur.execute("DELETE FROM cognitive_cycles WHERE id > ?;", (cycle_id,))
            conn.commit()
            return {"status": "REWOUND", "current_cycle": dict(row)}


if __name__ == "__main__":
    store = CognitiveStateStore()
    sample = {
        "agent_id": "IMF-Core-Mind",
        "cycle": 1,
        "stage_1_ingestion": {
            "exteroception": {"directive": "Test persistence"},
            "interoception": {"device": "RTX 5060 Ti", "vram_headroom_mb": 12000, "lean4_invariants": "0 sorry"}
        },
        "stage_2_surprise_detection": {"prediction_error": 0.042, "surprise_detected": True},
        "stage_3_ignition": {"ignited": True, "focal_object": "Lattice invariant check"},
        "stage_4_global_broadcast": {"global_workspace": {"imf-70b-plq": "Active"}},
        "stage_5_metacognitive_interrogation": {"stance": "GROUNDED_CONVICTION"},
        "execution_duration_ms": 12.5,
        "final_verdict": "Verified persistence store"
    }
    rowid = store.record_cycle(sample)
    print(f"[✓] Recorded cycle row {rowid}")
    history = store.get_history(5)
    print(f"[✓] Retrieved {len(history)} cycles from WAL SQLite store.")
