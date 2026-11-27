import numpy as np, pytest, torch


def hadamard(n):
    h = np.array([[1]])
    while h.shape[0] < n:
        h = np.block([[h, h], [h, -h]])
    return h

cuda = pytest.mark.skipif(not torch.cuda.is_available(), reason="no CUDA")


@cuda
def test_swiglu_backward_matches_autograd():
    from imf.kernels.triton_fused_swiglu_backward import swiglu_backward
    torch.manual_seed(0)
    N, D, F = 64, 48, 96
    x = torch.randn(N, D, device="cuda", requires_grad=True)
    wg = torch.randn(D, F, device="cuda", requires_grad=True)
    wu = torch.randn(D, F, device="cuda", requires_grad=True)
    do = torch.randn(N, F, device="cuda")
    (torch.nn.functional.silu(x @ wg) * (x @ wu)).backward(do)
    dx, dwg, dwu = swiglu_backward(do, x.detach(), wg.detach(), wu.detach())
    for a, b in ((dx, x.grad), (dwg, wg.grad), (dwu, wu.grad)):
        assert (a - b).abs().max().item() < 1e-3  # fp32 TF32-free matmul noise


@cuda
def test_rope_backward_matches_autograd():
    from imf.kernels.triton_fused_poincare_rope_backward import rope_forward, rope_backward
    torch.manual_seed(1)
    B, S, H = 2, 16, 32
    ang = torch.rand(S, H // 2, device="cuda") * 3
    cos, sin = ang.cos(), ang.sin()
    x = torch.randn(B, S, H, device="cuda", requires_grad=True)

    def ref(x):
        x0, x1 = x[..., 0::2], x[..., 1::2]
        return torch.stack((x0 * cos - x1 * sin, x0 * sin + x1 * cos), -1).flatten(-2)
    y = ref(x)
    assert (rope_forward(x.detach(), cos, sin) - y).abs().max().item() < 1e-5
    g = torch.randn_like(y)
    y.backward(g)
    assert (rope_backward(g, cos, sin) - x.grad).abs().max().item() < 1e-5


@cuda
def test_mla_latent_backward_exact_matches_autograd():
    from imf.kernels.triton_fused_poincare_mla_backward import mla_latent_backward_exact
    torch.manual_seed(2)
    N, L, D = 32, 16, 64
    c = torch.randn(N, L, device="cuda", requires_grad=True)
    wk, wv = torch.randn(L, D, device="cuda"), torch.randn(L, D, device="cuda")
    dK, dV = torch.randn(N, D, device="cuda"), torch.randn(N, D, device="cuda")
    ((c @ wk) * dK).sum().add_(((c @ wv) * dV).sum()).backward()
    assert (mla_latent_backward_exact(dK, dV, wk, wv) - c.grad).abs().max().item() < 1e-4


@pytest.mark.parametrize("D", [8, 64, 128, 256])
def test_rust_fwht_matches_hadamard_matrix(D):
    from imf.native_rust_bridge import get_rust_lib
    lib = get_rust_lib()
    if lib is None or not hasattr(lib, "imf_fast_walsh_hadamard_avx2"):
        pytest.skip("imf_fast_walsh_hadamard_avx2 Rust native library not built")
    from imf.native_rust_bridge import rust_fwht
    x = np.random.RandomState(D).randn(5, D).astype(np.float32)
    ref = x @ (hadamard(D).astype(np.float32) / np.sqrt(D))
    assert np.abs(rust_fwht(x) - ref).max() < 1e-4
    assert np.abs(np.linalg.norm(rust_fwht(x), axis=1) - np.linalg.norm(x, axis=1)).max() < 1e-4  # orthonormal


def test_rotation_cache_is_exact_and_hits():
    from imf.multimodal_cross_attention import ContinuousMultimodalCrossAttention as M
    torch.manual_seed(3)
    m = M(d_model=32, d_sensory=16, d_state=8).eval()
    h0, f = torch.zeros(1, 8), torch.randn(1, 16)
    with torch.no_grad():
        a = m.continuous_state_step(h0, f, 0.033)
        b = m.continuous_state_step(h0, f, 0.033)
    assert m.cache_misses == 1 and m.cache_hits == 1
    assert torch.equal(a, b)
    m.rotation_cache.clear()
    with torch.no_grad():
        c = m.continuous_state_step(h0, f, 0.033)
    assert torch.allclose(a, c, atol=1e-6)


def test_bloom_compaction_never_drops_distinct():
    from scripts.compact_parquet_lake_with_bloom_filter import BloomFilter
    bf = BloomFilter(2000, 0.05)
    items = [f"stmt_{i}" for i in range(2000)]
    flagged_distinct = sum(bf.add_check(s) for s in items)  # false positives only
    assert flagged_distinct < 0.15 * 2000
    assert all(bf.add_check(s) for s in items)  # no false negatives
