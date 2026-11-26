import ctypes
import time
import json
import torch
import numpy as np

def benchmark_polar_svd(so_path="csrc/fused_blackwell_bit_polar_svd.so"):
    lib = ctypes.CDLL(so_path)
    # void launch_fused_blackwell_bit_polar_svd(const float* A_in, float* U_out, float* S_out, float* V_out, int batch_size, cudaStream_t stream)
    lib.launch_fused_blackwell_bit_polar_svd.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_void_p
    ]
    lib.launch_fused_blackwell_bit_polar_svd.restype = None

    results = {}
    for batch_size in [128, 512, 1024, 4096]:
        A = torch.randn(batch_size, 16, 16, device='cuda', dtype=torch.float32)
        U = torch.zeros(batch_size, 16, 16, device='cuda', dtype=torch.float32)
        S = torch.zeros(batch_size, 16, device='cuda', dtype=torch.float32)
        V = torch.zeros(batch_size, 16, 16, device='cuda', dtype=torch.float32)

        # Warmup
        for _ in range(20):
            lib.launch_fused_blackwell_bit_polar_svd(
                ctypes.c_void_p(A.data_ptr()),
                ctypes.c_void_p(U.data_ptr()),
                ctypes.c_void_p(S.data_ptr()),
                ctypes.c_void_p(V.data_ptr()),
                batch_size, None
            )
        torch.cuda.synchronize()

        iters = 100
        start = time.perf_counter()
        for _ in range(iters):
            lib.launch_fused_blackwell_bit_polar_svd(
                ctypes.c_void_p(A.data_ptr()),
                ctypes.c_void_p(U.data_ptr()),
                ctypes.c_void_p(S.data_ptr()),
                ctypes.c_void_p(V.data_ptr()),
                batch_size, None
            )
        torch.cuda.synchronize()
        total_time = (time.perf_counter() - start) / iters
        results[batch_size] = {
            "latency_us": round(total_time * 1e6, 2),
            "throughput_mops": round((batch_size / total_time) / 1e6, 2)
        }
    return results

def benchmark_berry_phase(so_path="csrc/fused_blackwell_bit_berry_phase.so"):
    lib = ctypes.CDLL(so_path)
    # void launch_fused_blackwell_bit_berry_phase(const float* path_states_real, const float* path_states_imag, float* berry_phase_out, int batch_size, int num_loop_nodes, cudaStream_t stream)
    lib.launch_fused_blackwell_bit_berry_phase.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_void_p
    ]
    lib.launch_fused_blackwell_bit_berry_phase.restype = None

    results = {}
    num_loop_nodes = 8
    for batch_size in [256, 1024, 4096, 16384]:
        real = torch.randn(batch_size, num_loop_nodes, 16, device='cuda', dtype=torch.float32)
        imag = torch.randn(batch_size, num_loop_nodes, 16, device='cuda', dtype=torch.float32)
        out = torch.zeros(batch_size, device='cuda', dtype=torch.float32)

        for _ in range(20):
            lib.launch_fused_blackwell_bit_berry_phase(
                ctypes.c_void_p(real.data_ptr()),
                ctypes.c_void_p(imag.data_ptr()),
                ctypes.c_void_p(out.data_ptr()),
                batch_size, num_loop_nodes, None
            )
        torch.cuda.synchronize()

        iters = 100
        start = time.perf_counter()
        for _ in range(iters):
            lib.launch_fused_blackwell_bit_berry_phase(
                ctypes.c_void_p(real.data_ptr()),
                ctypes.c_void_p(imag.data_ptr()),
                ctypes.c_void_p(out.data_ptr()),
                batch_size, num_loop_nodes, None
            )
        torch.cuda.synchronize()
        total_time = (time.perf_counter() - start) / iters
        results[batch_size] = {
            "latency_us": round(total_time * 1e6, 2),
            "throughput_mops": round((batch_size / total_time) / 1e6, 2)
        }
    return results

def benchmark_rotor_slerp(so_path="csrc/fused_blackwell_bit_rotor_slerp.so"):
    lib = ctypes.CDLL(so_path)
    # void launch_fused_blackwell_bit_rotor_slerp(const float* r0_in, const float* r1_in, float* r_out, float t, int batch_size, cudaStream_t stream)
    lib.launch_fused_blackwell_bit_rotor_slerp.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_float, ctypes.c_int, ctypes.c_void_p
    ]
    lib.launch_fused_blackwell_bit_rotor_slerp.restype = None

    results = {}
    for batch_size in [1024, 4096, 16384, 65536]:
        r0 = torch.randn(batch_size, 4, device='cuda', dtype=torch.float32)
        r0 = torch.nn.functional.normalize(r0, p=2, dim=-1)
        r1 = torch.randn(batch_size, 4, device='cuda', dtype=torch.float32)
        r1 = torch.nn.functional.normalize(r1, p=2, dim=-1)
        out = torch.zeros(batch_size, 4, device='cuda', dtype=torch.float32)

        for _ in range(20):
            lib.launch_fused_blackwell_bit_rotor_slerp(
                ctypes.c_void_p(r0.data_ptr()),
                ctypes.c_void_p(r1.data_ptr()),
                ctypes.c_void_p(out.data_ptr()),
                0.5, batch_size, None
            )
        torch.cuda.synchronize()

        iters = 100
        start = time.perf_counter()
        for _ in range(iters):
            lib.launch_fused_blackwell_bit_rotor_slerp(
                ctypes.c_void_p(r0.data_ptr()),
                ctypes.c_void_p(r1.data_ptr()),
                ctypes.c_void_p(out.data_ptr()),
                0.5, batch_size, None
            )
        torch.cuda.synchronize()
        total_time = (time.perf_counter() - start) / iters
        results[batch_size] = {
            "latency_us": round(total_time * 1e6, 2),
            "throughput_mops": round((batch_size / total_time) / 1e6, 2)
        }
    return results

if __name__ == "__main__":
    print("Running hardware benchmarks on:", torch.cuda.get_device_name(0))
    res = {
        "device": torch.cuda.get_device_name(0),
        "polar_svd": benchmark_polar_svd(),
        "berry_phase": benchmark_berry_phase(),
        "rotor_slerp": benchmark_rotor_slerp()
    }
    with open("docs/benchmarks/reproducible_kernel_hardware_benchmark.json", "w") as f:
        json.dump(res, f, indent=2)
    print("Successfully recorded benchmark results:")
    print(json.dumps(res, indent=2))
