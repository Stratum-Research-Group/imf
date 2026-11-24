"""
imf/run_full_domain_oracle_eval.py
Automated Multi-Architecture Ground-Truth Oracle Benchmark Suite.
Evaluates code and reasoning generation across all 15 execution domains:
 x86-64 ASM, ARM64 ASM, RISC-V ASM, LLVM-IR, CUDA C++, C++20, eBPF, C17,
 Rust, Python, Lean 4, CRISPR, SMILES, Agentic JSON-RPC, and Triton.
"""

import sys
import json
import time
from pathlib import Path
from imf.domain_execution_verifiers import DomainExecutionVerifierRegistry

def run_suite():
    print("=" * 80)
    print("  IMF MULTI-ARCHITECTURE GROUND-TRUTH DOMAIN BENCHMARK SUITE")
    print("=" * 80)

    registry = DomainExecutionVerifierRegistry()
    results = {}

    benchmarks = [
        ("x86_64_asm", "mov rax, rbx\nadd rbx, 42\nret\n"),
        ("arm64_asm", "mov x0, x1\nadd x0, x0, #42\nret\n"),
        ("riscv_asm", "mv a0, a1\naddi a0, a0, 42\nret\n"),
        ("llvm_ir", "define i32 @add42(i32 %x) {\n  %res = add i32 %x, 42\n  ret i32 %res\n}\n"),
        ("cuda_cpp", "__global__ void add_kernel(float* a, float* b, float* c, int n) {\n  int i = blockDim.x * blockIdx.x + threadIdx.x;\n  if (i < n) c[i] = a[i] + b[i];\n}\n"),
        ("modern_cpp", "#include <concepts>\ntemplate<typename T>\nconcept Integral = std::is_integral_v<T>;\nIntegral auto add(Integral auto a, Integral auto b) { return a + b; }\n"),
        ("linux_ebpf", "#include <linux/bpf.h>\n#include <bpf/bpf_helpers.h>\nSEC(\"tracepoint/syscalls/sys_enter_write\")\nint bpf_prog(void *ctx) { return 0; }\nchar _license[] SEC(\"license\") = \"GPL\";\n"),
        ("c17_strict", "#include <stddef.h>\n#include <stdint.h>\nint safe_add(int32_t a, int32_t b, int32_t *res) {\n  if (!res) return -1;\n  *res = a + b;\n  return 0;\n}\n"),
        ("rust_strict", "pub fn safe_divide(num: u64, denom: u64) -> Option<u64> {\n  if denom == 0 { None } else { Some(num / denom) }\n}\n"),
        ("python_algo", "def solve(n: int) -> int:\n    return sum(i for i in range(n) if i % 3 == 0 or i % 5 == 0)\nassert solve(10) == 23\n"),
        ("lean4_formal", "theorem add_comm_imf (a b : Nat) : a + b = b + a := by\n  omega\n"),
        ("crispr_genomics", "ATGCGATCGATCGATCGATCGATCGATCAGG"),
        ("cheminformatics_smiles", "CC(=O)Oc1ccccc1C(=O)O"),  # Aspirin
        ("agentic_json_rpc", json.dumps({"jsonrpc": "2.0", "method": "imf_verify_polytope", "params": {"polytope_dim": 8, "n_vertices": 240}, "id": 1})),
        ("triton_kernel", "@triton.jit\ndef dummy_kernel(x_ptr, y_ptr, n_elements, BLOCK_SIZE: tl.constexpr):\n    pass\n")
    ]

    passed = 0
    total = len(benchmarks)

    for domain, payload in benchmarks:
        t0 = time.perf_counter()
        verified = False
        msg = ""

        try:
            if domain == "x86_64_asm":
                verified, msg = registry.verify_x86_assembly(payload)
            elif domain == "arm64_asm":
                verified, msg = registry.verify_arm64_assembly(payload)
            elif domain == "riscv_asm":
                verified, msg = registry.verify_riscv_assembly(payload)
            elif domain == "llvm_ir":
                verified, msg = registry.verify_llvm_ir(payload)
            elif domain == "cuda_cpp":
                verified, msg = registry.verify_cuda(payload)
            elif domain == "modern_cpp":
                verified, msg = registry.verify_cpp20(payload)
            elif domain == "linux_ebpf":
                verified, msg = registry.verify_ebpf(payload)
            elif domain == "c17_strict":
                verified, msg = registry.verify_c17(payload)
            elif domain == "rust_strict":
                verified, msg = registry.verify_rust(payload)
            elif domain == "python_algo":
                verified, msg = registry.verify_python_execution(payload)
            elif domain == "lean4_formal":
                verified, msg = registry.verify_lean4(payload, theorem_name="add_comm_imf")
            elif domain == "crispr_genomics":
                verified, msg = registry.verify_genomics_dna(payload)
            elif domain == "cheminformatics_smiles":
                verified, msg = registry.verify_smiles_valency(payload)
            elif domain == "agentic_json_rpc":
                verified, msg = registry.verify_tool_call_json(payload, required_keys=["jsonrpc", "method", "id"])
            elif domain == "triton_kernel":
                verified, msg = registry.verify_triton_kernel(payload)
        except Exception as e:
            verified = False
            msg = str(e)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        status = "[PASS]" if verified else "[SKIP/FAIL]"
        if verified:
            passed += 1

        results[domain] = {
            "verified": verified,
            "latency_ms": round(elapsed_ms, 2),
            "output": msg
        }

        print(f"  {status:<11} {domain:<24} | Latency: {elapsed_ms:7.2f} ms | Info: {msg[:45]}")

    print("=" * 80)
    print(f"Summary: {passed}/{total} Verified Domains Operational ({passed/total*100:.1f}%)")
    print("=" * 80)

    out_file = Path("dist/DOMAIN_EXECUTION_EVAL_REPORT.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_suite()
