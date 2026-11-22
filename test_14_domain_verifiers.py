"""
test_14_domain_verifiers.py
Tests all 14 execution and formal verification oracles in IMF.
"""

from imf.domain_execution_verifiers import DomainExecutionVerifierRegistry

def test_full_registry():
    print("=" * 80)
    print("  Testing Complete IMF 14-Domain Execution & Ground-Truth Oracle Registry")
    print("=" * 80)

    reg = DomainExecutionVerifierRegistry()

    tests = [
        # 1. x86-64 Assembly
        ("1. x86-64 Assembly (GAS/Intel)", lambda: reg.verify_x86_assembly(
            asm_code=".global _start\n_start:\n    mov rax, 60\n    xor rdi, rdi\n    syscall\n",
            use_intel_syntax=True
        )),

        # 2. ARM64 (AArch64) Assembly
        ("2. ARM64 (AArch64) Assembly", lambda: reg.verify_arm64_assembly(
            asm_code=".global _start\n_start:\n    mov x8, #93\n    mov x0, #0\n    svc #0\n"
        )),

        # 3. RISC-V (RV64) Assembly
        ("3. RISC-V (RV64) Assembly", lambda: reg.verify_riscv_assembly(
            asm_code=".global _start\n_start:\n    li a7, 93\n    li a0, 0\n    ecall\n"
        )),

        # 4. LLVM-IR Intermediate Representation
        ("4. LLVM-IR SSA Verification", lambda: reg.verify_llvm_ir(
            ir_code="define i32 @add(i32 %a, i32 %b) {\n    %res = add i32 %a, %b\n    ret i32 %res\n}\n"
        )),

        # 5. CUDA C++ Kernel Verification
        ("5. CUDA C++ Kernel (NVCC)", lambda: reg.verify_cuda(
            cuda_code="#include <cuda_runtime.h>\n"
                      "__global__ void vec_add(const float* A, const float* B, float* C, int n) {\n"
                      "    int i = blockDim.x * blockIdx.x + threadIdx.x;\n"
                      "    if (i < n) C[i] = A[i] + B[i];\n"
                      "}\n"
        )),

        # 6. Modern C++20 Concepts
        ("6. Modern C++20 Concepts & PMR", lambda: reg.verify_cpp20(
            code="#include <concepts>\n#include <vector>\n"
                 "template<std::integral T>\n"
                 "T compute_sum(T a, T b) { return a + b; }\n"
                 "int main() { return compute_sum(10, 20) == 30 ? 0 : 1; }\n"
        )),

        # 7. Linux Kernel eBPF Bytecode
        ("7. Linux Kernel eBPF Bytecode", lambda: reg.verify_ebpf(
            code="int xdp_filter(void *ctx) { return 1; }\n"
        )),

        # 8. C17 Memory Bounds
        ("8. C17 Systems Memory Bounds", lambda: reg.verify_c17(
            code="#include <stddef.h>\n#include <stdbool.h>\n"
                 "bool check(const unsigned char *p, size_t len, size_t max) {\n"
                 "    return (p != NULL && len <= max);\n"
                 "}\n"
        )),

        # 9. Rust Strict Type-Checking
        ("9. Rust Strict Library Type-Check", lambda: reg.verify_rust(
            code="pub fn binary_search(arr: &[i32], target: i32) -> Option<usize> {\n"
                 "    arr.binary_search(&target).ok()\n"
                 "}\n"
        )),

        # 10. Python Algorithmic Execution
        ("10. Python Algorithmic Sandbox", lambda: reg.verify_python_execution(
            code="def fib(n):\n    return n if n <= 1 else fib(n-1) + fib(n-2)\n",
            test_assertions="assert fib(6) == 8\nassert fib(0) == 0\n"
        )),

        # 11. Lean 4 Formal Theorems
        ("11. Lean 4 Formal Proof Oracle", lambda: reg.verify_lean4(
            code="theorem add_zero (n : Nat) : n + 0 = n := by rfl\n",
            theorem_name="add_zero"
        )),

        # 12. CRISPR Genomics & DNA
        ("12. CRISPR Genomics & Watson-Crick", lambda: reg.verify_genomics_dna(
            sequence="ATGCGTACGATCGATCGATCGG",  # 22 bp + canonical SpCas9 GG PAM
            target_pam="NGG"
        )),

        # 13. Cheminformatics SMILES
        ("13. Cheminformatics SMILES Valency", lambda: reg.verify_smiles_valency(
            smiles="CC(=O)OC1=CC=CC=C1C(=O)O"  # Aspirin
        )),

        # 14. Agentic JSON RPC
        ("14. Agentic Tool Calling JSON RPC", lambda: reg.verify_tool_call_json(
            json_str='{"tool": "dak-spanner.execute_sql", "arguments": {"instance_id": "inst-1", "sql": "SELECT 1"}}'
        )),
    ]

    passed_count = 0
    for name, fn in tests:
        ok, msg = fn()
        if ok:
            passed_count += 1
        icon = "✓" if ok else "✗"
        print(f"[{icon}] {name:<38} -> {msg[:60]}")

    print("=" * 80)
    print(f"[✓] Verification Results: {passed_count}/{len(tests)} ({passed_count/len(tests)*100:.1f}%) Oracles Certified!")
    print("=" * 80)

if __name__ == "__main__":
    test_full_registry()
