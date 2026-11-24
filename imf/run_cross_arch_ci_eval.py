"""
imf/run_cross_arch_ci_eval.py
Automated Cross-Architecture Assembly & Toolchain Verification Benchmark.
Validates code generation across low-level architectures: x86-64, ARM64, RISC-V, LLVM-IR,
and Linux eBPF using deterministic system compilers (GNU as, Clang, opt).
"""

import time
import json
from pathlib import Path
from imf.domain_execution_verifiers import DomainExecutionVerifierRegistry

def run_cross_arch_eval():
    print("=" * 80)
    print("  IMF CROSS-ARCHITECTURE LOW-LEVEL SYSTEM VERIFICATION BENCHMARK")
    print("  Target Architectures: x86-64, ARM64, RISC-V (RV64), LLVM-IR, Linux eBPF")
    print("=" * 80)

    registry = DomainExecutionVerifierRegistry()
    test_cases = [
        ("x86_64_polytope_dot", "x86_64", """
.globl dot_product
dot_product:
    xorps %xmm0, %xmm0
    ret
"""),
        ("arm64_neon_vector_add", "arm64", """
.globl vector_add
vector_add:
    fadd v0.4s, v0.4s, v1.4s
    ret
"""),
        ("riscv_rv64_accumulate", "riscv", """
.globl rv64_accumulate
rv64_accumulate:
    add a0, a0, a1
    ret
"""),
        ("llvm_ir_simd_fma", "llvm_ir", """
define <4 x float> @fma_simd(<4 x float> %a, <4 x float> %b, <4 x float> %c) {
  %prod = fmul <4 x float> %a, %b
  %res = fadd <4 x float> %prod, %c
  ret <4 x float> %res
}
"""),
        ("linux_ebpf_socket_filter", "ebpf", """
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
SEC("socket")
int filter_prog(struct __sk_buff *skb) {
    return 0;
}
char _license[] SEC("license") = "GPL";
""")
    ]

    results = []
    passed = 0
    t0 = time.perf_counter()

    for name, arch, code in test_cases:
        t_sub = time.perf_counter()
        verified = False
        msg = ""

        if arch == "x86_64":
            verified, msg = registry.verify_x86_assembly(code, use_intel_syntax=False)
        elif arch == "arm64":
            verified, msg = registry.verify_arm64_assembly(code)
        elif arch == "riscv":
            verified, msg = registry.verify_riscv_assembly(code)
        elif arch == "llvm_ir":
            verified, msg = registry.verify_llvm_ir(code)
        elif arch == "ebpf":
            verified, msg = registry.verify_ebpf(code)

        elapsed_ms = (time.perf_counter() - t_sub) * 1000.0
        status = "[PASS]" if verified else "[FAIL]"
        if verified:
            passed += 1

        results.append({
            "name": name,
            "arch": arch,
            "verified": verified,
            "latency_ms": round(elapsed_ms, 2),
            "info": msg
        })

        print(f"  {status:<8} {name:<28} | Arch: {arch:<8} | Latency: {elapsed_ms:6.2f} ms")
        print(f"    Info: {msg[:60]}")

    total_elapsed = time.perf_counter() - t0
    acc = (passed / len(test_cases)) * 100.0

    print("=" * 80)
    print(f"[✓] Cross-Architecture Benchmark Completed: {passed}/{len(test_cases)} Passed ({acc:.1f}%) in {total_elapsed:.2f}s")
    print("=" * 80)

    out_p = Path("dist/CROSS_ARCH_CI_EVAL_REPORT.json")
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_cross_arch_eval()
