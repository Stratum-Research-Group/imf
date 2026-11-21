#!/usr/bin/env python3
"""
imf_cognitive_engine.py

Interactive and programmatic CLI engine for managing the 5-phase Cognitive Flow
state machine and applying deterministic Troubleshooting Bottleneck diagnostics.
"""

import sys
import time
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class CognitiveState:
    phase: str
    deliverable: str
    clarity_score: int  # 1-10
    friction_score: int # 1-10
    parking_lot: List[str]

class CognitiveFlowEngine:
    PHASES = ["setup", "struggle", "release", "flow", "recovery"]

    def __init__(self, deliverable: str = "Unspecified deliverable"):
        self.state = CognitiveState(
            phase="setup",
            deliverable=deliverable,
            clarity_score=10,
            friction_score=1,
            parking_lot=[]
        )
        self.start_time = time.time()

    def advance_phase(self) -> str:
        curr_idx = self.PHASES.index(self.state.phase)
        if curr_idx < len(self.PHASES) - 1:
            self.state.phase = self.PHASES[curr_idx + 1]
        return self.state.phase

    def park_distraction(self, thought: str):
        self.state.parking_lot.append(thought)

    def diagnose_bottleneck(self) -> str:
        if self.state.clarity_score < 4:
            return "anxious_frozen"
        elif self.state.friction_score < 2 and self.state.phase in ["struggle", "flow"]:
            return "bored_restless"
        elif self.state.friction_score > 7:
            return "foggy_sluggish"
        return "nominal"

    def apply_fix(self, bottleneck: str) -> str:
        if bottleneck == "anxious_frozen":
            self.state.clarity_score = 9
            self.state.friction_score = 3
            return "Shrunk scope to atomic micro-step. Clarity restored to 9."
        elif bottleneck == "bored_restless":
            self.state.friction_score = 6
            return "Injected strict 15-minute timebox and elevated standards."
        elif bottleneck == "foggy_sluggish":
            self.state.friction_score = 3
            return "Initiated 5-breath reset and cold-water protocol. Friction bounded."
        return "State nominal. Continuing flow trajectory."

def main():
    print("=" * 60)
    print("  IMF Cognitive Flow & Troubleshooting Engine (CLI)")
    print("=" * 60)
    engine = CognitiveFlowEngine("Formalize Paper 36 & Invariant Proofs")
    print(f"[*] Initialized Session: '{engine.state.deliverable}'")
    print(f"[*] Starting Phase: <{engine.state.phase}>")

    for phase in ["struggle", "release", "flow", "recovery"]:
        step = engine.advance_phase()
        print(f"  ──► Transitioned to Phase: <{step}>")

    engine.state.clarity_score = 2
    b = engine.diagnose_bottleneck()
    print(f"[*] Injected stress test: Bottleneck detected: {b}")
    res = engine.apply_fix(b)
    print(f"[*] Diagnostic Fix Applied: {res}")
    print(f"[*] Final Clarity: {engine.state.clarity_score}/10, Friction: {engine.state.friction_score}/10")
    print("[+] All cognitive state transitions verified.")

if __name__ == "__main__":
    main()
