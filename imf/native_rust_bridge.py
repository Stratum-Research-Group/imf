"""
imf/native_rust_bridge.py
ctypes-based high-performance bridge to the native Rust `imf_rs` shared library (`libimf_rs.so`).
Enables zero-copy foreign-function interface (FFI) bindings for:
1. Cayley manifold transform and Lie algebra projections.
2. Direct SHM ring buffer telemetry.
3. Fast CPU-side matrix inversion benchmarks.
"""

import os
import ctypes
from typing import Optional, Dict, Any, Tuple
import numpy as np

_LIB_IMF_RS = None

def get_rust_lib():
    global _LIB_IMF_RS
    if _LIB_IMF_RS is not None:
        return _LIB_IMF_RS
        
    candidates = [
        os.path.abspath("imf_rs/target/release/libimf_rs.so"),
        os.path.abspath("imf_rs/target/debug/libimf_rs.so"),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                lib = ctypes.CDLL(p)
                lib.imf_benchmark_inversion.restype = ctypes.c_double
                lib.imf_benchmark_inversion.argtypes = [ctypes.c_uint32]
                
                lib.imf_cayley_step_cpu.restype = ctypes.c_int32
                lib.imf_cayley_step_cpu.argtypes = [
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.c_size_t
                ]
                if hasattr(lib, "imf_rs_infer_batch"):
                    lib.imf_rs_infer_batch.restype = ctypes.c_int32
                    lib.imf_rs_infer_batch.argtypes = [
                        ctypes.POINTER(ctypes.c_float),
                        ctypes.POINTER(ctypes.c_float),
                        ctypes.POINTER(ctypes.c_float),
                        ctypes.c_size_t,
                        ctypes.c_size_t,
                        ctypes.c_size_t,
                        ctypes.POINTER(ctypes.c_uint32),
                        ctypes.POINTER(ctypes.c_float),
                    ]
                if hasattr(lib, "imf_polytope_projection_avx2"):
                    lib.imf_polytope_projection_avx2.restype = ctypes.c_int32
                    lib.imf_polytope_projection_avx2.argtypes = [
                        ctypes.POINTER(ctypes.c_float),
                        ctypes.POINTER(ctypes.c_float),
                        ctypes.c_size_t,
                        ctypes.c_size_t,
                        ctypes.c_size_t,
                        ctypes.POINTER(ctypes.c_float),
                        ctypes.POINTER(ctypes.c_uint32),
                    ]
                if hasattr(lib, "imf_fast_walsh_hadamard_avx2"):
                    lib.imf_fast_walsh_hadamard_avx2.restype = ctypes.c_int32
                    lib.imf_fast_walsh_hadamard_avx2.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_size_t, ctypes.c_size_t]
                if hasattr(lib, "imf_shm_ring_consume_batch_avx2"):
                    lib.imf_shm_ring_consume_batch_avx2.restype = ctypes.c_int32
                    lib.imf_shm_ring_consume_batch_avx2.argtypes = [
                        ctypes.POINTER(ctypes.c_float),
                        ctypes.POINTER(ctypes.c_float),
                        ctypes.c_size_t,
                        ctypes.c_size_t
                    ]
                _LIB_IMF_RS = lib
                return _LIB_IMF_RS
            except Exception as e:
                pass
    return None

def is_rust_accelerator_available() -> bool:
    return get_rust_lib() is not None

def benchmark_rust_inversion(iterations: int = 1000) -> float:
    lib = get_rust_lib()
    if lib is None:
        raise RuntimeError("Native Rust accelerator library `libimf_rs.so` not found.")
    return lib.imf_benchmark_inversion(iterations)

def rust_cayley_step_cpu(x: np.ndarray, a: np.ndarray) -> np.ndarray:
    """
    Executes native Rust Cayley retraction: y = (I - A/2)^{-1} (I + A/2) x
    """
    lib = get_rust_lib()
    if lib is None:
        raise RuntimeError("Native Rust accelerator library `libimf_rs.so` not found.")
        
    x_c = np.ascontiguousarray(x, dtype=np.float32)
    a_c = np.ascontiguousarray(a, dtype=np.float32)
    dim = len(x_c)
    assert a_c.shape == (dim, dim)
    
    y = np.empty_like(x_c)
    
    status = lib.imf_cayley_step_cpu(
        x_c.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        a_c.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        y.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        dim
    )
    if status != 0:
        raise RuntimeError(f"Rust Cayley transform failed with code {status}")
    return y


def rust_infer_batch(
    states: np.ndarray,
    a_mats: np.ndarray,
    head_weights: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Batched zero-copy token inference via native Rust SIMD bridge.
    Args:
        states: [B, D] float32
        a_mats: [B, D, D] float32 skew-symmetric generator matrices
        head_weights: [V, D] float32 language model projection weights
    Returns:
        next_states: [B, D] float32 updated in-place
        tokens: [B] uint32 predicted token ids
        drifts: [B] float32 drift norms
    """
    lib = get_rust_lib()
    if lib is None or not hasattr(lib, "imf_rs_infer_batch"):
        raise RuntimeError("Native Rust batched infer function `imf_rs_infer_batch` not found.")

    states_c = np.ascontiguousarray(states, dtype=np.float32)
    a_mats_c = np.ascontiguousarray(a_mats, dtype=np.float32)
    head_c = np.ascontiguousarray(head_weights, dtype=np.float32)

    B, D = states_c.shape
    V = head_c.shape[0]

    out_tokens = np.zeros(B, dtype=np.uint32)
    out_drifts = np.zeros(B, dtype=np.float32)

    status = lib.imf_rs_infer_batch(
        states_c.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        a_mats_c.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        head_c.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        B,
        D,
        V,
        out_tokens.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
        out_drifts.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
    )
    if status != 0:
        raise RuntimeError(f"Rust batched inference failed with code {status}")

    return states_c, out_tokens, out_drifts


def rust_polytope_projection_avx2(
    vectors: np.ndarray,
    vertices: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Batched AVX2/FMA projection of vectors onto polytope vertices.
    Args:
        vectors: [N, D] float32 query vectors
        vertices: [V, D] float32 polytope vertices
    Returns:
        projected: [N, D] float32 closest/maximal vertex vectors
        indices: [N] uint32 indices of chosen vertices
    """
    lib = get_rust_lib()
    if lib is None or not hasattr(lib, "imf_polytope_projection_avx2"):
        raise RuntimeError("Native Rust polytope projection function `imf_polytope_projection_avx2` not found.")

    v_in = np.ascontiguousarray(vectors, dtype=np.float32)
    vert_in = np.ascontiguousarray(vertices, dtype=np.float32)

    N, D = v_in.shape
    V, D2 = vert_in.shape
    assert D == D2, f"Dimension mismatch: vectors {D} vs vertices {D2}"

    out_proj = np.empty_like(v_in)
    out_indices = np.zeros(N, dtype=np.uint32)

    status = lib.imf_polytope_projection_avx2(
        v_in.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        vert_in.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        N,
        V,
        D,
        out_proj.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        out_indices.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
    )
    if status != 0:
        raise RuntimeError(f"Rust polytope projection failed with code {status}")

    return out_proj, out_indices




def rust_fwht(x: np.ndarray) -> np.ndarray:
    """Orthonormal Walsh-Hadamard transform of [B, D] (D power of two). Returns a new array."""
    lib = get_rust_lib()
    if lib is None or not hasattr(lib, "imf_fast_walsh_hadamard_avx2"):
        raise RuntimeError("imf_fast_walsh_hadamard_avx2 not found")
    y = np.array(x, dtype=np.float32, order="C", copy=True)
    if y.ndim == 1:
        y = y[None]
    st = lib.imf_fast_walsh_hadamard_avx2(y.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), y.shape[0], y.shape[1])
    if st != 0:
        raise RuntimeError(f"FWHT failed with code {st}")
    return y


def rust_shm_ring_consume_batch(src: np.ndarray, dst: np.ndarray) -> None:
    lib = get_rust_lib()
    if lib is None or not hasattr(lib, "imf_shm_ring_consume_batch_avx2"):
        raise RuntimeError("imf_shm_ring_consume_batch_avx2 not found")
    assert src.flags.c_contiguous and dst.flags.c_contiguous
    assert src.shape == dst.shape
    st = lib.imf_shm_ring_consume_batch_avx2(
        src.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        dst.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        src.shape[0],
        src.shape[1] if src.ndim > 1 else 1
    )
    if st != 0:
        raise RuntimeError(f"SHM ring consumer failed with code {st}")
