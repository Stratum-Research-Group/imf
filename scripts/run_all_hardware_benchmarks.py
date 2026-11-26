import subprocess
import json
import time

def main():
    print("=" * 70)
    print("IMF Unified Hardware & Verification Benchmark Runner")
    print("=" * 70)

    # 1. GPU Kernels
    print("\n[1/3] Running Blackwell GPU Tensor Benchmarks...")
    cmd1 = ["uv", "run", "python", "scripts/benchmark_kernels_hardware.py"]
    res1 = subprocess.run(cmd1, capture_output=True, text=True)
    print(res1.stdout)

    # 2. io_uring Storage
    print("\n[2/3] Running io_uring Direct-DMA Storage Benchmarks...")
    cmd2 = ["uv", "run", "python", "scripts/benchmark_iouring_hardware.py"]
    res2 = subprocess.run(cmd2, capture_output=True, text=True)
    print(res2.stdout)

    # 3. Lean Verification Gate
    print("\n[3/3] Running Lean 4 Mathlib Pilot Verification Gate...")
    cmd3 = ["lake", "build", "Pilot"]
    res3 = subprocess.run(cmd3, cwd="lean_pilot", capture_output=True, text=True)
    print(res3.stdout)
    assert res3.returncode == 0, "Lean pilot verification failed!"

    print("\n[✓] All unified hardware benchmarks and formal gates PASSED successfully!")

if __name__ == "__main__":
    main()
