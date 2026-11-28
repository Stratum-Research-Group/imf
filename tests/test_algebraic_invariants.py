"""
tests/test_algebraic_invariants.py
Property-based invariant testing verifying algebraic theorems certified in Lean 4
Module 83 (Pilot.LieRollingCacheStability) using high-precision double-precision (Float64) arithmetic.
Includes automatic pure-NumPy execution fallback when PyTorch is not installed.
Tests:
1. Theorem 1 (Lie Commutator Trace Zero): Tr([A, B]) = 0.
2. Theorem 2 (Lie Algebra Antisymmetry): Omega + Omega^T = 0.
3. Theorem 3 (Orthogonal Frobenius Isometry): ||U M U^T||_F = ||M||_F.
4. Theorem 4 (Rank-1 Skew Nil-Trace): Tr(v^T k - k^T v) = 0.
5. Dissipative Contraction: ||lambda U M U^T||_F <= ||M||_F for lambda in (0, 1].
"""
import numpy as np

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


def test_theorem_1_lie_bracket_nil_trace():
    d = 32
    if HAS_TORCH:
        for _ in range(20):
            A = torch.randn(d, d, dtype=torch.float64)
            B = torch.randn(d, d, dtype=torch.float64)
            comm = A @ B - B @ A
            tr = torch.trace(comm).item()
            assert abs(tr) < 1e-12, f"Commutator trace non-zero: {tr}"
    else:
        rng = np.random.default_rng(42)
        for _ in range(20):
            A = rng.standard_normal((d, d))
            B = rng.standard_normal((d, d))
            comm = A @ B - B @ A
            tr = np.trace(comm)
            assert abs(tr) < 1e-12, f"Commutator trace non-zero: {tr}"


def test_theorem_2_antisymmetry():
    d = 32
    if HAS_TORCH:
        for _ in range(20):
            v = torch.randn(d, dtype=torch.float64)
            k = torch.randn(d, dtype=torch.float64)
            W = torch.outer(v, k) - torch.outer(k, v)
            sum_skew = W + W.T
            assert torch.max(torch.abs(sum_skew)).item() < 1e-12
    else:
        rng = np.random.default_rng(42)
        for _ in range(20):
            v = rng.standard_normal(d)
            k = rng.standard_normal(d)
            W = np.outer(v, k) - np.outer(k, v)
            sum_skew = W + W.T
            assert np.max(np.abs(sum_skew)) < 1e-12


def test_theorem_3_orthogonal_frobenius_isometry():
    d = 32
    if HAS_TORCH:
        for _ in range(20):
            A = torch.randn(d, d, dtype=torch.float64)
            A = 0.5 * (A - A.T)
            I = torch.eye(d, dtype=torch.float64)
            U = torch.linalg.solve(I - 0.5 * A, I + 0.5 * A)

            # Check U is orthogonal
            assert torch.max(torch.abs(U.T @ U - I)).item() < 1e-12

            M = torch.randn(d, d, dtype=torch.float64)
            norm_orig = torch.linalg.norm(M, 'fro').item()
            norm_rot = torch.linalg.norm(U @ M @ U.T, 'fro').item()
            assert abs(norm_rot - norm_orig) / norm_orig < 1e-12
    else:
        rng = np.random.default_rng(42)
        for _ in range(20):
            A = rng.standard_normal((d, d))
            A = 0.5 * (A - A.T)
            I = np.eye(d)
            U = np.linalg.solve(I - 0.5 * A, I + 0.5 * A)

            # Check U is orthogonal
            assert np.max(np.abs(U.T @ U - I)) < 1e-12

            M = rng.standard_normal((d, d))
            norm_orig = np.linalg.norm(M, 'fro')
            norm_rot = np.linalg.norm(U @ M @ U.T, 'fro')
            assert abs(norm_rot - norm_orig) / norm_orig < 1e-12


def test_theorem_4_rank1_skew_trace_vanishing():
    d = 32
    if HAS_TORCH:
        for _ in range(20):
            v = torch.randn(d, dtype=torch.float64)
            k = torch.randn(d, dtype=torch.float64)
            W = torch.outer(v, k) - torch.outer(k, v)
            tr = torch.trace(W).item()
            assert abs(tr) < 1e-12
    else:
        rng = np.random.default_rng(42)
        for _ in range(20):
            v = rng.standard_normal(d)
            k = rng.standard_normal(d)
            W = np.outer(v, k) - np.outer(k, v)
            tr = np.trace(W)
            assert abs(tr) < 1e-12


def test_dissipative_lyapunov_contraction():
    d = 32
    for lam in [0.99, 0.95, 0.90, 0.80]:
        if HAS_TORCH:
            A = torch.randn(d, d, dtype=torch.float64)
            A = 0.5 * (A - A.T)
            I = torch.eye(d, dtype=torch.float64)
            U = torch.linalg.solve(I - 0.5 * A, I + 0.5 * A)

            M = torch.randn(d, d, dtype=torch.float64)
            norm_orig = torch.linalg.norm(M, 'fro').item()
            M_next = lam * (U @ M @ U.T)
            norm_next = torch.linalg.norm(M_next, 'fro').item()
            assert norm_next <= norm_orig + 1e-12
        else:
            rng = np.random.default_rng(42)
            A = rng.standard_normal((d, d))
            A = 0.5 * (A - A.T)
            I = np.eye(d)
            U = np.linalg.solve(I - 0.5 * A, I + 0.5 * A)

            M = rng.standard_normal((d, d))
            norm_orig = np.linalg.norm(M, 'fro')
            M_next = lam * (U @ M @ U.T)
            norm_next = np.linalg.norm(M_next, 'fro')
            assert norm_next <= norm_orig + 1e-12


if __name__ == "__main__":
    test_theorem_1_lie_bracket_nil_trace()
    test_theorem_2_antisymmetry()
    test_theorem_3_orthogonal_frobenius_isometry()
    test_theorem_4_rank1_skew_trace_vanishing()
    test_dissipative_lyapunov_contraction()
    print("ALL 5 LEAN INVARIANT PROPERTY TESTS PASSED WITH MACHINE PRECISION IDENTITY!")
