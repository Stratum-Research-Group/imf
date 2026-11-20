import pytest
from imf.execution_verifier import MultiLanguageExecutionVerifier


def test_python_verifier():
    verifier = MultiLanguageExecutionVerifier()
    valid_py = "def add(x: int, y: int) -> int:\n    return x + y\n"
    invalid_py = "def add(x: int y: int):\n    return x +\n"

    ok, _ = verifier.verify_python(valid_py)
    assert ok is True

    bad, _ = verifier.verify_python(invalid_py)
    assert bad is False


def test_rust_verifier():
    verifier = MultiLanguageExecutionVerifier()
    valid_rs = "pub fn add(a: i32, b: i32) -> i32 { a + b }\n"
    ok, _ = verifier.verify_rust(valid_rs)
    assert ok is True


def test_lean4_verifier():
    verifier = MultiLanguageExecutionVerifier()
    valid_lean = "theorem id_nat (n : Nat) : n = n := by rfl\n"
    ok, _ = verifier.verify_lean4(valid_lean)
    assert ok is True
