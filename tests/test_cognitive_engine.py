import pytest
from imf.cognitive_engine import CognitiveFlowEngine, CognitiveState

def test_cognitive_flow_lifecycle():
    engine = CognitiveFlowEngine("Implement and verify Lean 4 cognitive specs")
    assert engine.state.phase == "setup"
    
    assert engine.advance_phase() == "struggle"
    assert engine.advance_phase() == "release"
    assert engine.advance_phase() == "flow"
    assert engine.advance_phase() == "recovery"
    # Idempotent terminal boundary
    assert engine.advance_phase() == "recovery"

def test_distraction_parking_lot():
    engine = CognitiveFlowEngine("Deep Work Session")
    engine.park_distraction("Check email about server outage")
    engine.park_distraction("Order more loose leaf tea")
    assert len(engine.state.parking_lot) == 2
    assert "Check email about server outage" in engine.state.parking_lot

def test_bottleneck_diagnostics_and_fixes():
    engine = CognitiveFlowEngine("Debugging hard kernel issue")
    engine.state.phase = "struggle"
    
    # Anxious/Frozen
    engine.state.clarity_score = 2
    assert engine.diagnose_bottleneck() == "anxious_frozen"
    engine.apply_fix("anxious_frozen")
    assert engine.state.clarity_score >= 8
    
    # Bored/Restless
    engine.state.friction_score = 1
    assert engine.diagnose_bottleneck() == "bored_restless"
    engine.apply_fix("bored_restless")
    assert engine.state.friction_score >= 5
    
    # Foggy/Sluggish
    engine.state.friction_score = 9
    assert engine.diagnose_bottleneck() == "foggy_sluggish"
    engine.apply_fix("foggy_sluggish")
    assert engine.state.friction_score < 5
