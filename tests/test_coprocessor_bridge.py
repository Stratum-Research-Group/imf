import pytest
import torch
from imf.coprocessor_bridge import IMFCoprocessorBridge


def test_coprocessor_bridge_initialization():
    bridge = IMFCoprocessorBridge(device="cpu")
    assert bridge.verifier is not None


def test_coprocessor_python_verification():
    bridge = IMFCoprocessorBridge(device="cpu")
    code = "def add(a, b):\n    return a + b\nprint(add(2, 3))"
    res = bridge.verify_python_execution(code=code, expected_output="5")
    assert res["verified"] is True
    assert res["stdout"] == "5"


def test_coprocessor_lean4_verification():
    bridge = IMFCoprocessorBridge(device="cpu")
    lean_code = "theorem test_add_zero (n : Nat) : n + 0 = n := by rfl"
    res = bridge.verify_lean4_code(lean_code)
    assert res["verified"] is True
    assert res["exit_code"] == 0
