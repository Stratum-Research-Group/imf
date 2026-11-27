import pytest
import numpy as np

from imf.native_rust_bridge import is_rust_accelerator_available, benchmark_rust_inversion, rust_cayley_step_cpu

def test_rust_accelerator_bridge():
    from imf.native_rust_bridge import get_rust_lib
    lib = get_rust_lib()
    if lib is None or not hasattr(lib, "imf_polytope_projection_avx2"):
        pytest.skip("imf_polytope_projection_avx2 Rust native library not built")
    """Validates FFI linkage to libimf_rs.so and execution correctness."""
    assert is_rust_accelerator_available(), "libimf_rs.so should be compiled and linkable"
    res = benchmark_rust_inversion(1000)
    assert res > 0.0
    
    dim = 8
    x = np.ones(dim, dtype=np.float32)
    A = np.zeros((dim, dim), dtype=np.float32) # Zero skew-symmetric matrix -> Identity Cayley transform
    y = rust_cayley_step_cpu(x, A)
    np.testing.assert_allclose(y, x, atol=1e-4)
