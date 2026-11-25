"""
Triton RoPE forward + backward.
Scope note: this is standard (Euclidean) rotary embedding on pairs (x[2i], x[2i+1]).
It is NOT conformally mapped into the Poincare ball; the rotation is orthogonal, so
the exact backward is the inverse rotation (angle -> -angle).
"""
import torch
import triton
import triton.language as tl


@triton.jit
def _rope_kernel(x_ptr, cos_ptr, sin_ptr, out_ptr, S, H: tl.constexpr, SIGN: tl.constexpr):
    row = tl.program_id(0)          # row over [B*S]
    s = row % S
    i = tl.arange(0, H // 2)
    base = row * H
    x0 = tl.load(x_ptr + base + 2 * i)
    x1 = tl.load(x_ptr + base + 2 * i + 1)
    c = tl.load(cos_ptr + s * (H // 2) + i)
    sn = tl.load(sin_ptr + s * (H // 2) + i) * SIGN
    tl.store(out_ptr + base + 2 * i, x0 * c - x1 * sn)
    tl.store(out_ptr + base + 2 * i + 1, x0 * sn + x1 * c)


def _run(x, cos, sin, sign):
    B, S, H = x.shape
    x = x.contiguous()
    out = torch.empty_like(x)
    _rope_kernel[(B * S,)](x, cos.contiguous(), sin.contiguous(), out, S, H=H, SIGN=sign)
    return out


def rope_forward(x, cos, sin):
    return _run(x, cos, sin, 1.0)


def rope_backward(grad_out, cos, sin):
    return _run(grad_out, cos, sin, -1.0)
