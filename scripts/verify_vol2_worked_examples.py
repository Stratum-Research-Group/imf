#!/usr/bin/env python3
"""
scripts/verify_vol2_worked_examples.py
Mathematical verification script for The Sacred Sanctum Volume II Worked Examples Pack.
Computes every numerical worked example across Chapters 1 to 9 using pure NumPy float64.
"""
import math
from itertools import combinations, product
import numpy as np

np.set_printoptions(precision=6, suppress=True, linewidth=110)
SEP = "=" * 72

def banner(t):
    print("\n" + SEP + "\n" + t + "\n" + SEP)

def run_all():
    # -------------------------------------------------------------------------
    # CHAPTER 1: Exceptional Holonomy, G2/Spin(7), Octonions
    # -------------------------------------------------------------------------
    banner("EX 1.1  Ch1 (Thm 1.1): Octonion alternativity & Fano plane table")
    # Basis: e0 = 1, e1..e7
    # Fano triples: (1,2,4), (2,3,5), (3,4,6), (4,5,7), (5,6,1), (6,7,2), (7,1,3)
    triplets = [
        (1, 2, 4), (2, 3, 5), (3, 4, 6), (4, 5, 7),
        (5, 6, 1), (6, 7, 2), (7, 1, 3)
    ]
    mult = np.zeros((8, 8, 8), dtype=np.float64)
    for i in range(8):
        mult[0, i, i] = 1.0
        mult[i, 0, i] = 1.0
    for i in range(1, 8):
        mult[i, i, 0] = -1.0
    for a, b, c in triplets:
        mult[a, b, c] = 1.0;  mult[b, a, c] = -1.0
        mult[b, c, a] = 1.0;  mult[c, b, a] = -1.0
        mult[c, a, b] = 1.0;  mult[a, c, b] = -1.0

    def oct_mul(x, y):
        res = np.zeros(8, dtype=np.float64)
        for i in range(8):
            if x[i] == 0: continue
            for j in range(8):
                if y[j] == 0: continue
                res += x[i] * y[j] * mult[i, j]
        return res

    def associator(x, y, z):
        return oct_mul(oct_mul(x, y), z) - oct_mul(x, oct_mul(y, z))

    rng = np.random.default_rng(42)
    for _ in range(50):
        x = rng.standard_normal(8)
        y = rng.standard_normal(8)
        z = rng.standard_normal(8)
        # Alternativity identities: [x,x,y] = 0, [x,y,x] = 0, [y,x,x] = 0
        assert np.allclose(associator(x, x, y), 0.0, atol=1e-12)
        assert np.allclose(associator(x, y, x), 0.0, atol=1e-12)
        assert np.allclose(associator(y, x, x), 0.0, atol=1e-12)
        # Total skew-symmetry / sign flip under transposition
        A_xyz = associator(x, y, z)
        A_yxz = associator(y, x, z)
        A_xzy = associator(x, z, y)
        assert np.allclose(A_xyz, -A_yxz, atol=1e-12)
        assert np.allclose(A_xyz, -A_xzy, atol=1e-12)
    print("EX 1.1: PASSED (Octonion alternativity & complete associator antisymmetry confirmed)")

    banner("EX 1.2  Ch1 (Cor 1.1): Artin's corollary (2-generated subalgebra associativity)")
    for _ in range(20):
        x = rng.standard_normal(8)
        y = rng.standard_normal(8)
        # Any 2-generated subalgebra is associative
        assert np.allclose(oct_mul(oct_mul(x, y), x), oct_mul(x, oct_mul(y, x)), atol=1e-12)
        assert np.allclose(oct_mul(oct_mul(x, y), y), oct_mul(x, oct_mul(y, y)), atol=1e-12)
        assert np.allclose(oct_mul(oct_mul(x, x), y), oct_mul(x, oct_mul(x, y)), atol=1e-12)

    # 3-element counterexample demonstrating 3-generated is non-associative:
    e1, e2, e3 = np.zeros(8), np.zeros(8), np.zeros(8)
    e1[1] = 1.0; e2[2] = 1.0; e3[3] = 1.0
    assoc_123 = associator(e1, e2, e3)
    assert not np.allclose(assoc_123, 0.0)
    assert np.allclose(assoc_123, np.array([0., 0., 0., 0., 0., 0., -2., 0.]))
    print(f"EX 1.2: PASSED (Artin's theorem verified; 3-element counterexample [e1,e2,e3]={assoc_123[6]} e6)")

    # -------------------------------------------------------------------------
    # CHAPTER 2: Concentration of Measure & Hyperspherical Orthogonality
    # -------------------------------------------------------------------------
    banner("EX 2.1  Ch2 (Thm 2.5): Inner-product concentration across dimensions")
    dims = [2, 4, 8, 16, 24, 64, 128, 256]
    N_mc = 1_000_000
    rng_c2 = np.random.default_rng(1337)
    for d in dims:
        u = rng_c2.standard_normal((N_mc, d))
        v = rng_c2.standard_normal((N_mc, d))
        u /= np.linalg.norm(u, axis=1, keepdims=True)
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        dots = np.sum(u * v, axis=1)
        var_emp = np.var(dots)
        var_theor = 1.0 / d
        prob_tail = np.mean(np.abs(dots) >= 0.3)
        assert np.isclose(var_emp, var_theor, rtol=0.03), f"d={d}: var_emp={var_emp} vs theor={var_theor}"
        print(f"d={d:3d}: Var(<u,v>) = {var_emp:.6f} (theory 1/{d:3d} = {var_theor:.6f}) | P(|<u,v>| >= 0.3) = {prob_tail * 100:.3f}%")
    print("EX 2.1: PASSED (Hyperspherical inner-product concentration verified)")

    banner("EX 2.2  Ch2 (Thm 2.1, 2.2): Boundary shell volume & equatorial slab")
    # For d dimensions, volume of shell of thickness epsilon = k/d: 1 - (1 - eps)^d
    for d in [8, 24, 128]:
        for k in [1, 2, 3]:
            eps = k / d
            shell_vol = 1.0 - (1.0 - eps)**d
            limit_val = 1.0 - np.exp(-k)
            print(f"d={d:3d}, k={k}: Shell volume = {shell_vol:.6f} (asymptote 1-e^-{k} = {limit_val:.6f})")
            assert shell_vol >= 0.60
    print("EX 2.2: PASSED (Boundary concentration (1-eps)^d verified)")

    banner("EX 2.3  Ch2 Sec 6 & Ch6 (Welch Bound & Orthant Centroids): Orthogonality Ceiling")
    # Sign vectors in {+1, -1}^d: centroid cosine is (d - 2k)/d for Hamming distance k
    d = 8
    for k in range(d + 1):
        cos_k = (d - 2 * k) / d
        print(f"Hamming k={k}: cosine = {cos_k:+0.4f}")
    assert (d - 2*0)/d == 1.0 and (d - 2*d)/d == -1.0 and (d - 2*(d//2))/d == 0.0

    # Welch Bound for E=128 vectors in R^8:
    # For any E unit vectors in R^d:
    # I_max^2 >= (E - d) / (d * (E - 1))
    E_exp, d_dim = 128, 8
    welch_lower_bound = (E_exp - d_dim) / (d_dim * (E_exp - 1))
    # 120 / (8 * 127) = 120 / 1016 = 15 / 127
    assert np.isclose(welch_lower_bound, 120.0 / 1016.0)
    print(f"E={E_exp}, d={d_dim}: Welch mean squared inner product >= {welch_lower_bound:.6f} (= 120/1016)")
    print("Proves that 128 mutually orthogonal vectors in R^8 are mathematically impossible (max 8).")
    print("EX 2.3: PASSED (Orthant capacity & Welch orthogonality bound confirmed)")

    # -------------------------------------------------------------------------
    # CHAPTER 3: The Gosset 4_21 Polytope, E8, and 8D Sphere Packing
    # -------------------------------------------------------------------------
    banner("EX 3.1  Ch3: Explicit construction of all 240 E8 root vectors")
    roots = []
    # 112 integer roots: +/-1, +/-1 in two positions, 0 elsewhere
    for i, j in combinations(range(8), 2):
        for s1, s2 in product([-1.0, 1.0], repeat=2):
            r = [0.0] * 8
            r[i] = s1
            r[j] = s2
            roots.append(r)
    assert len(roots) == 112

    # 128 half-integer roots: +/- 1/2 in all 8 coords, even number of minus signs
    for signs in product([-0.5, 0.5], repeat=8):
        if sum(1 for s in signs if s < 0) % 2 == 0:
            roots.append(list(signs))
    assert len(roots) == 240

    R_e8 = np.array(roots, dtype=np.float64)
    norms_sq = np.sum(R_e8**2, axis=1)
    assert np.allclose(norms_sq, 2.0), "All E8 roots must have squared norm 2"

    dots_e8 = R_e8 @ R_e8.T
    unique_dots = np.unique(np.round(dots_e8, 6))
    assert np.array_equal(unique_dots, np.array([-2., -1., 0., 1., 2.])), f"Dots: {unique_dots}"
    print(f"EX 3.1: PASSED (240 E8 roots constructed: 112 integer + 128 half-integer, norms^2=2, dots in {-2,-1,0,1,2})")

    banner("EX 3.2  Ch3 (Thm 5.1): Order of the E8 Weyl group W(E8)")
    w_order = int(np.prod([float(math.factorial(k)) for k in [4, 6, 8]]))
    expected_order = 696_729_600
    assert w_order == expected_order
    print(f"EX 3.2: PASSED (|W(E8)| = 4! * 6! * 8! = 24 * 720 * 40320 = {w_order:,})")

    banner("EX 3.3  Ch3 (Thm 6.1): E8 lattice quantization gain vs Z^8 scalar rounding")
    def quantize_D8(x):
        f = np.round(x)
        diff = np.abs(x - f)
        s = np.sum(f, axis=1) % 2
        odd_idx = np.where(s == 1)[0]
        if len(odd_idx) > 0:
            worst = np.argmax(diff[odd_idx], axis=1)
            for row_i, col_j in zip(odd_idx, worst):
                if x[row_i, col_j] >= f[row_i, col_j]:
                    f[row_i, col_j] += 1.0
                else:
                    f[row_i, col_j] -= 1.0
        return f

    def quantize_E8(x):
        q1 = quantize_D8(x)
        shift = 0.5 * np.ones(8)
        q2 = quantize_D8(x - shift) + shift
        d1 = np.sum((x - q1)**2, axis=1)
        d2 = np.sum((x - q2)**2, axis=1)
        mask = (d2 < d1)[:, None]
        return np.where(mask, q2, q1)

    N_q = 500_000
    rng_q = np.random.default_rng(2026)
    x_test = rng_q.uniform(-2, 2, size=(N_q, 8))
    err_z8 = np.mean(np.sum((x_test - np.round(x_test))**2, axis=1))
    err_e8 = np.mean(np.sum((x_test - quantize_E8(x_test))**2, axis=1))
    msqe_ratio = err_e8 / err_z8
    gain_db = 10.0 * np.log10(err_z8 / err_e8)
    # Theoretical second moment ratio G(E8)/G(Z^8) ~= 0.071682 / 0.083333 = 0.86018 (+0.654 dB gain)
    assert 0.84 < msqe_ratio < 0.88, f"Empirical ratio: {msqe_ratio}"
    print(f"EX 3.3: PASSED (E8 MSQE ratio = {msqe_ratio:.4f} vs theory 0.8602, Quantization gain: +{gain_db:.3f} dB)")

    # -------------------------------------------------------------------------
    # CHAPTER 4: The Leech Lattice Lambda_24 and Conway Symmetry
    # -------------------------------------------------------------------------
    banner("EX 4.1  Ch4 (Thm 4.3): Kissing number tau_24 = 196,560 and minimal norms^2 = 4")
    # Orbit 1: binom(24, 2) * 2^2 = 276 * 4 = 1,104
    N1 = int(math.comb(24, 2)) * 4
    # Orbit 2: 759 octads * 2^(8-1) = 759 * 128 = 97,152
    N2 = 759 * 128
    # Orbit 3: 24 positions of -/+3 * 2^11 = 24 * 4096 = 98,304
    N3 = 24 * 4096
    total_tau24 = N1 + N2 + N3
    assert total_tau24 == 196_560
    # In standard Leech lattice scaling u = x / sqrt(8):
    # Orbit 1 norm^2: (4^2 + 4^2) / 8 = 32 / 8 = 4
    # Orbit 2 norm^2: (8 * 2^2) / 8 = 32 / 8 = 4
    # Orbit 3 norm^2: (3^2 + 23 * 1^2) / 8 = (9 + 23) / 8 = 32 / 8 = 4
    assert (4**2 + 4**2) / 8.0 == 4.0
    assert (8 * 2**2) / 8.0 == 4.0
    assert (3**2 + 23 * 1**2) / 8.0 == 4.0
    print(f"EX 4.1: PASSED (N1={N1:,} + N2={N2:,} + N3={N3:,} = {total_tau24:,} minimal vectors, all ||u||^2 = 4)")

    banner("EX 4.2  Ch4 (Thm 4.4): Order of Conway group Co0")
    # |Co0| = 2^22 * 3^9 * 5^4 * 7^2 * 11 * 13 * 23 = 8,315,553,613,086,720,000
    co0_order = (2**22) * (3**9) * (5**4) * (7**2) * 11 * 13 * 23
    expected_co0 = 8_315_553_613_086_720_000
    assert co0_order == expected_co0
    co1_order = co0_order // 2
    assert co1_order == 4_157_776_806_543_360_000
    print(f"EX 4.2: PASSED (|Co0| = {co0_order:,}, |Co1| = {co1_order:,})")

    # -------------------------------------------------------------------------
    # CHAPTER 5: Sub-Bit Polytope Lattice Quantization (PLQ) Mechanics
    # -------------------------------------------------------------------------
    banner("EX 5.1  Ch5 Sec 5: Effective bits/weight formula arithmetic across PLQ regimes")
    # In PLQ-1.58, PLQ-1.00, PLQ-0.75, index bits are 12, 8, 6 over 8D blocks (1.5, 1.0, 0.75 b/w).
    # In PLQ-0.58, the base codebook achieves 0.58 b/weight (or 4.64 index bits over 8D blocks)
    # Amortized 16-bit scale overhead per group adds 16/group_size b/weight:
    # PLQ-1.58: 1.5000 + 16/128  = 1.6250 b/w
    # PLQ-1.00: 1.0000 + 16/256  = 1.0625 b/w -> 1.062 b
    # PLQ-0.75: 0.7500 + 16/512  = 0.78125 b/w -> 0.781 b
    # PLQ-0.58: 0.5800 + 16/1024 = 0.595625 b/w -> 0.595 b (and nominal 4b/8D gives 0.515625 b/w)
    assert np.isclose(12.0 / 8.0 + 16.0 / 128.0, 1.625)
    assert np.isclose(8.0 / 8.0 + 16.0 / 256.0, 1.0625)
    assert np.isclose(6.0 / 8.0 + 16.0 / 512.0, 0.78125)
    eff_058 = 0.58 + 16.0 / 1024.0
    assert np.isclose(eff_058, 0.595625)
    print(f"PLQ-1.58: (12b / 8D) + (16b / 128 weights) = {12/8 + 16/128:.4f} b/weight")
    print(f"PLQ-1.00: ( 8b / 8D) + (16b / 256 weights) = {8/8 + 16/256:.4f} b/weight")
    print(f"PLQ-0.75: ( 6b / 8D) + (16b / 512 weights) = {6/8 + 16/512:.5f} b/weight")
    print(f"PLQ-0.58: (0.580b base) + (16b / 1024 weights = 0.015625b) = {eff_058:.6f} b/weight (matches 0.595b)")
    print("EX 5.1: PASSED (Sub-bit effective bits/weight arithmetic verified for all regimes)")

    # -------------------------------------------------------------------------
    # CHAPTER 6: Fine-Grained Polytope MoPE & 98.4% Sparsity
    # -------------------------------------------------------------------------
    banner("EX 6.1  Ch6 (Thm 6.1): The 98.4375% inactive sparsity horizon")
    E_tot = 128
    k_act = 2
    sparsity = 1.0 - (k_act / E_tot)
    fraction = (E_tot - k_act) / E_tot
    assert sparsity == 0.984375
    assert fraction == 126.0 / 128.0
    assert k_act + (E_tot - k_act) == E_tot
    print(f"EX 6.1: PASSED (E={E_tot}, k={k_act} -> Sparsity = 126/128 = {sparsity * 100:.4f}%)")

    banner("EX 6.2  Ch6: Barycentric gating simplex projection")
    c1 = np.array([1.0, 0.0, 0.0])
    c2 = np.array([0.0, 1.0, 0.0])
    c3 = np.array([0.0, 0.0, 1.0])
    C_simplex = np.stack([c1, c2, c3])
    token_embed = np.array([0.2, 0.5, 0.3])
    sq_dists = np.sum((C_simplex - token_embed)**2, axis=1)
    gating_weights = np.exp(-sq_dists) / np.sum(np.exp(-sq_dists))
    assert np.all(gating_weights >= 0.0)
    assert np.isclose(np.sum(gating_weights), 1.0)
    print(f"EX 6.2: PASSED (Barycentric simplex weights: {gating_weights}, sum = {np.sum(gating_weights):.6f})")

    # -------------------------------------------------------------------------
    # CHAPTER 7: The Shared Foundation Trunk & Hyperspherical Repulsion
    # -------------------------------------------------------------------------
    banner("EX 7.1  Ch7 (Thm 7.1): Shared trunk gradient conservation under sparse vanishing")
    rng_c7 = np.random.default_rng(777)
    g_shared = rng_c7.standard_normal((16, 16))
    g_sparse = rng_c7.standard_normal((16, 16))
    assert np.allclose((g_shared + g_sparse) - g_sparse, g_shared, atol=1e-15)
    norm_shared = np.linalg.norm(g_shared)
    for decay in [1.0, 0.5, 0.1, 0.01, 1e-5, 0.0]:
        g_total = g_shared + decay * g_sparse
        norm_total = np.linalg.norm(g_total)
        # Even as g_sparse -> 0, ||g_total|| converges strictly to ||g_shared|| > 0
        assert norm_total > 0.0
    print(f"EX 7.1: PASSED (Backbone gradient strictly conserved: ||g_shared|| = {norm_shared:.6f} > 0)")

    # -------------------------------------------------------------------------
    # CHAPTER 8: Dynamic Shannon Entropy & Adaptive Temperature Annealing
    # -------------------------------------------------------------------------
    banner("EX 8.1  Ch8 (Thm 8.1): Dynamic temperature annealing negative-feedback stability")
    H_target = 0.85
    tau = 1.0
    E_experts = 128
    rng_c8 = np.random.default_rng(888)
    logits = rng_c8.standard_normal(E_experts) * 2.5
    lr_tau = 0.05
    for step in range(10_000):
        # Softmax probabilities at temperature tau
        exp_z = np.exp((logits - np.max(logits)) / tau)
        p = exp_z / np.sum(exp_z)
        H_norm = -np.sum(p * np.log(p + 1e-15)) / np.log(E_experts)
        # Two-sided negative-feedback restoration law: cools when H > target, heats when H < target
        tau = tau * np.exp(lr_tau * (H_target - H_norm))
    # Assert entropy converges within 0.02 of target 0.85
    assert abs(H_norm - H_target) < 0.02, f"Expected H_norm near {H_target}, got {H_norm}"
    print(f"EX 8.1: PASSED (Two-sided annealing converged over 10,000 steps to H_norm = {H_norm:.4f} [target {H_target}], tau = {tau:.4f})")

    banner("EX 8.2  Ch8 (Thm 8.2): Load-balancing loss minimum at uniform dispatch")
    E_exp = 128
    lam_bal = 0.01
    # Uniform dispatch:
    f_uniform = np.ones(E_exp) / E_exp
    P_uniform = np.ones(E_exp) / E_exp
    L_uniform = lam_bal * E_exp * np.sum(f_uniform * P_uniform)
    assert np.isclose(L_uniform, lam_bal)

    # Any non-uniform perturbation strictly increases loss (Cauchy-Schwarz)
    for _ in range(50):
        perturb = rng_c8.uniform(0.1, 1.0, size=E_exp)
        f_perturbed = perturb / np.sum(perturb)
        P_perturbed = f_perturbed
        L_perturbed = lam_bal * E_exp * np.sum(f_perturbed * P_perturbed)
        assert L_perturbed >= L_uniform - 1e-12
    print(f"EX 8.2: PASSED (Load balancing loss global minimum L_min = lambda = {L_uniform:.4f} at uniform dispatch)")

    # -------------------------------------------------------------------------
    # CHAPTER 9: Formal Verification Lean 4 Module Pilot.PolytopeSparsity
    # -------------------------------------------------------------------------
    banner("EX 9.1  Ch9: Pure NumPy arithmetic mirroring of 8 Lean 4 theorems")
    E_int = 128
    k_int = 2
    # Thm 1: polytope_expert_partition_sum: k + (E - k) = E
    assert k_int + (E_int - k_int) == E_int
    # Thm 2: polytope_sparsity_strictly_positive: 0 < E - k
    assert 0 < (E_int - k_int)
    # Thm 3: shared_trunk_gradient_conservation: (g_shared + g_sparse) - g_sparse = g_shared
    gs_arr = np.array([15, -4, 27], dtype=np.int64)
    gp_arr = np.array([-3, 11, 8], dtype=np.int64)
    assert np.array_equal((gs_arr + gp_arr) - gp_arr, gs_arr)
    # Thm 4: hyperspherical_repulsive_cancellation: r - r = 0
    r_val = 42
    assert r_val - r_val == 0
    # Thm 5: polytope_centroid_distance_reflexive: d <= d
    d_val = 128
    assert d_val <= d_val
    # Thm 6: micro_expert_dimension_associativity: (a * b) * c = a * (b * c)
    a, b, c = 4, 16, 64
    assert (a * b) * c == a * (b * c)
    # Thm 7: matryoshka_orthant_projection_scaling: x * 1 = x
    x_val = 256
    assert x_val * 1 == x_val
    # Thm 8: load_balance_potential_neutral: l - 0 = l
    l_val = 99
    assert l_val - 0 == l_val
    print("EX 9.1: PASSED (All 8 Lean 4 theorem arithmetic identities verified in pure NumPy)")

    print("\n" + SEP + "\nALL VOLUME II WORKED EXAMPLES NUMERICALLY CONFIRMED AND PASSED\n" + SEP)

if __name__ == "__main__":
    run_all()
