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
from typing import Optional, Dict, Any
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
