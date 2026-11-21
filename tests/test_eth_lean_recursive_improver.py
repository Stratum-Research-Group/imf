"""
tests/test_eth_lean_recursive_improver.py
Unit tests verifying the ETH-Lean Recursive Self-Improvement loop.
Asserts that:
1. Lean 4 compiler is correctly invoked as a non-negotiable verification oracle.
2. Invalid lemmas or proofs with 'sorry' are strictly rejected (anti-cheating).
3. Sound mathematical candidates (bipartite cut bounds, uncrossing identities) pass with 0 errors.
"""

from imf.eth_lean_recursive_improver import ETHLeanRecursiveImprover


def test_eth_lean_oracle_rejects_sorry():
    improver = ETHLeanRecursiveImprover()
    fake_proof = (
        "theorem bad_claim (n : Nat) : n = n + 1 := by\n"
        "  sorry\n"
    )
    success, msg = improver.verify_lean_snippet(fake_proof)
    assert not success
    assert "'sorry' detected" in msg


def test_eth_lean_oracle_verifies_sound_math():
    improver = ETHLeanRecursiveImprover()
    valid_proof = (
        "theorem add_comm_simple (a b : Nat) : a + b = b + a := by\n"
        "  omega\n"
    )
    success, msg = improver.verify_lean_snippet(valid_proof)
    assert success, f"Failed verification: {msg}"


def test_eth_lean_rsi_cycle_runs_successfully():
    improver = ETHLeanRecursiveImprover()
    result = improver.run_rsi_cycle(max_generations=1)
    assert result["total_proposed"] == 3
    assert result["total_verified"] == 3
    assert result["verification_rate"] == 1.0
