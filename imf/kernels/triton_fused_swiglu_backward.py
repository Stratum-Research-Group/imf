"""
Fused SwiGLU elementwise backward (Triton).
out = silu(g) * u, with g = x@Wg, u = x@Wu.
Given dout, g, u, computes dg and du in one pass, recomputing silu(g) in
registers instead of storing it (saves one [N,F] activation tensor).
Scope: the elementwise stage only; dx / dW are cuBLAS matmuls (see swiglu_backward).
"""
import torch
import triton
import triton.language as tl


@triton.jit
def _swiglu_bwd_kernel(dout_ptr, g_ptr, u_ptr, dg_ptr, du_ptr, n, BLOCK: tl.constexpr):
    offs = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    m = offs < n
    do = tl.load(dout_ptr + offs, mask=m).to(tl.float32)
    g = tl.load(g_ptr + offs, mask=m).to(tl.float32)
    u = tl.load(u_ptr + offs, mask=m).to(tl.float32)
    s = tl.sigmoid(g)
    silu = g * s
    dsilu = s * (1.0 + g * (1.0 - s))
    tl.store(dg_ptr + offs, do * u * dsilu, mask=m)
    tl.store(du_ptr + offs, do * silu, mask=m)


def swiglu_elementwise_backward(dout, g, u):
    dout, g, u = dout.contiguous(), g.contiguous(), u.contiguous()
    dg, du = torch.empty_like(g), torch.empty_like(u)
    n = g.numel()
    _swiglu_bwd_kernel[(triton.cdiv(n, 1024),)](dout, g, u, dg, du, n, BLOCK=1024)
    return dg, du


def swiglu_backward(dout, x, wg, wu):
    """Full backward: returns dx, dwg, dwu. x:[N,D], wg/wu:[D,F], dout:[N,F]."""
    g, u = x @ wg, x @ wu
    dg, du = swiglu_elementwise_backward(dout, g, u)
    return dg @ wg.T + du @ wu.T, x.T @ dg, x.T @ du
