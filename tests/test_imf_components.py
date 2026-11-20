"""
Unit and integration tests for IMF (Interaction Model Foundations).
Validates:
  1. Polytope Connector coordinate extraction & simplex properties.
  2. Multi-token interaction over higher-arity simplex hyperfaces (Arity-3 and Arity-4).
  3. FusedSAVGLayer forward, backward autograd gradient flow, and shape contracts.
"""

import pytest
import torch
from polytope_connector import ConfigurablePolytopeConnector
from higher_arity_simplex import HigherAritySimplexBinding
from triton_savg_kernel import FusedSAVGLayer, pytorch_reference_savg_scan


@pytest.mark.parametrize("preset,expected_vertices", [
    ("tetrahedron", 4),
    ("enneazetton_simplex", 10),
    ("enneazetton_orthoplex", 18),
    ("decayotton_simplex", 11),
    ("decayotton_orthoplex", 20),
    ("hendecaxennon_simplex", 12),
    ("hendecaxennon_orthoplex", 22),
])
def test_polytope_connector_initialization(preset, expected_vertices):
    d_model = 64
    connector = ConfigurablePolytopeConnector(d_model=d_model, preset=preset)
    assert connector.num_vertices == expected_vertices

    x = torch.randn(4, 16, d_model)
    coords = connector.get_coordinates(x)
    assert coords.shape == (4, 16, expected_vertices)
    assert torch.allclose(coords.sum(dim=-1), torch.ones(4, 16), atol=1e-5)


@pytest.mark.parametrize("preset", ["tetrahedron", "decayotton_orthoplex"])
def test_polytope_grid_modulation(preset):
    d_model = 32
    connector = ConfigurablePolytopeConnector(d_model=d_model, preset=preset)
    x = torch.randn(2, 8, d_model)
    grid_mod = connector.compute_grid_modulation(x)
    assert grid_mod.shape == (2, 8, 1, 1)
    assert torch.all(grid_mod > 0)


@pytest.mark.parametrize("arity", [3, 4])
def test_higher_arity_simplex_binding(arity):
    batch, seq_len, d_model = 2, 8, 32
    binding_module = HigherAritySimplexBinding(d_model=d_model, arity=arity, rank=8, num_corners=6)
    tokens = [torch.randn(batch, seq_len, d_model) for _ in range(arity)]

    out = binding_module(tokens)
    assert out.shape == (batch, seq_len, d_model)
    assert not torch.isnan(out).any()
    assert not torch.isinf(out).any()


def test_fused_savg_layer_autograd_and_shapes():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    d_model = 32
    layer = FusedSAVGLayer(d_model=d_model, preset="decayotton_orthoplex").to(device)
    x = torch.randn(2, 16, d_model, device=device, requires_grad=True)

    out = layer(x)
    assert out.shape == (2, 16, d_model)
    assert not torch.isnan(out).any()

    # Test backward gradient flow
    loss = out.sum()
    loss.backward()
    assert x.grad is not None
    for name, p in layer.named_parameters():
        assert p.grad is not None, f"Parameter {name} has no gradient!"


@pytest.mark.parametrize("dtype", [torch.float16, torch.bfloat16, torch.float32])
def test_fused_savg_layer_dtypes(dtype):
    device = torch.device("cpu")
    d_model = 16
    layer = FusedSAVGLayer(d_model=d_model, preset="tetrahedron").to(device=device, dtype=dtype)
    x = torch.randn(2, 4, d_model, device=device, dtype=dtype, requires_grad=True)

    out = layer(x, use_triton=False)
    assert out.shape == (2, 4, d_model)
    assert out.dtype == dtype
    assert not torch.isnan(out).any()

    loss = out.sum()
    loss.backward()
    assert x.grad is not None
    assert x.grad.dtype == dtype


def test_fused_savg_streaming_step_equivalence():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    d_model = 32
    batch = 2
    layer = FusedSAVGLayer(d_model=d_model, preset="tetrahedron").to(device)

    state = layer.init_state(batch, device)
    x_t = torch.randn(batch, d_model, device=device)

    out_tri, state_tri = layer.step(x_t, state, use_triton=True)
    out_ref, state_ref = layer.step(x_t, state, use_triton=False)

    assert out_tri.shape == (batch, d_model)
    assert state_tri[0].shape == (batch, d_model, d_model)
    assert state_tri[1].shape == (batch, d_model, d_model)

    max_diff_out = (out_tri - out_ref).abs().max().item()
    max_diff_s = (state_tri[0] - state_ref[0]).abs().max().item()
    max_diff_a = (state_tri[1] - state_ref[1]).abs().max().item()

    assert max_diff_out < 1e-4
    assert max_diff_s < 1e-4
    assert max_diff_a < 1e-4


def test_imf_language_model_forward_and_generate():
    from pretrain_imf_lm import IMFLanguageModel
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    vocab_size = 50
    d_model = 32
    lm = IMFLanguageModel(vocab_size=vocab_size, d_model=d_model, n_layers=2, preset="tetrahedron").to(device)

    # 1. Forward batch
    tokens = torch.randint(0, vocab_size, (2, 8), device=device)
    logits = lm(tokens)
    assert logits.shape == (2, 8, vocab_size)

    # 2. Streaming step
    states = lm.init_streaming_states(batch_size=1, device=device)
    curr_tok = torch.tensor([[5]], device=device)
    step_logits, next_states = lm.generate_step(curr_tok.squeeze(1), states)
    assert step_logits.shape == (1, vocab_size)
    assert len(next_states) == 2


def test_multihead_savg_layer():
    from multihead_savg import MultiHeadSAVGLayer
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    B, T, D, H = 2, 8, 32, 4
    layer = MultiHeadSAVGLayer(d_model=D, num_heads=H, preset="tetrahedron").to(device)

    x = torch.randn(B, T, D, device=device, requires_grad=True)
    out = layer(x)
    assert out.shape == (B, T, D)

    # Autograd flow
    loss = out.sum()
    loss.backward()
    assert x.grad is not None

    # Streaming step
    state = layer.init_state(B, device)
    x_t = torch.randn(B, D, device=device)
    step_out, next_st = layer.step(x_t, state)
    assert step_out.shape == (B, D)
    assert next_st[0].shape == (B, H, D // H, D // H)


def test_triton_backward_kernel_equivalence():
    """Verify that fused Triton backward matches analytic adjoint backward within tight tolerance."""
    from triton_savg_kernel import HAS_TRITON, analytic_savg_backward, SAVGScanFunction
    if not (HAS_TRITON and torch.cuda.is_available()):
        pytest.skip("CUDA or Triton not available")

    B, T, D = 4, 16, 32
    U = torch.randn(B, T, D, device="cuda")
    V = torch.randn(B, T, D, device="cuda")
    Q = torch.randn(B, T, D, device="cuda")
    g = torch.sigmoid(torch.randn(B, T, device="cuda"))
    dOut = torch.randn(B, T, D, device="cuda")

    gU_ref, gV_ref, gQ_ref, gg_ref = analytic_savg_backward(U, V, Q, g, dOut)

    # Test via SAVGScanFunction autograd backward with use_triton=True
    U1 = U.clone().requires_grad_()
    V1 = V.clone().requires_grad_()
    Q1 = Q.clone().requires_grad_()
    g1 = g.clone().requires_grad_()

    out_triton = SAVGScanFunction.apply(U1, V1, Q1, g1, 0.999, 0.990, True)
    torch.autograd.backward(out_triton, dOut)

    assert torch.allclose(U1.grad, gU_ref, atol=1e-4)
    assert torch.allclose(V1.grad, gV_ref, atol=1e-4)
    assert torch.allclose(Q1.grad, gQ_ref, atol=1e-4)
    assert torch.allclose(g1.grad, gg_ref, atol=1e-4)




