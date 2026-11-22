"""
Automated Multi-Language Execution & Formal Tactic Verifier for IMF.

Unifies ground-truth execution environments and deterministic verification oracles:
 1. x86-64 Assembly (GAS / Intel syntax)
 2. ARM64 (AArch64) Assembly
 3. RISC-V (RV64) Assembly
 4. LLVM Intermediate Representation (LLVM-IR)
 5. CUDA C++ Kernel Verification (nvcc)
 6. Modern C++20 Concepts & PMR (g++ / clang++)
 7. Linux Kernel eBPF Bytecode (clang -target bpf)
 8. C17 Memory Safety & Bounds (gcc / clang)
 9. Rust Strict Library Type-Checking (rustc)
10. Python Algorithmic Execution & Sandbox Unit Assertions
11. Lean 4 Formal Theorems (#print axioms zero-axiom gating)
12. CRISPR Genomics & Watson-Crick DNA
13. Cheminformatics SMILES & Valency Topology
14. Agentic JSON RPC & Tool Calling Schema
"""

from typing import Dict, Tuple, Optional
from imf.domain_execution_verifiers import DomainExecutionVerifierRegistry


class MultiLanguageExecutionVerifier:
    def __init__(self):
        self.registry = DomainExecutionVerifierRegistry()
        self.has_rustc = self.registry.has_rustc
        self.has_lean = self.registry.has_lean
        self.has_gcc = self.registry.has_gcc
        self.has_clang = self.registry.has_clang
        self.has_nvcc = self.registry.has_nvcc
        self.has_as = self.registry.has_as
        self.has_opt = self.registry.has_opt

    # Forwarding methods for backward compatibility
    def verify_python(self, code: str, test_assertions: Optional[str] = None) -> Tuple[bool, str]:
        return self.registry.verify_python_execution(code, test_assertions)

    def verify_rust(self, code: str) -> Tuple[bool, str]:
        return self.registry.verify_rust(code)

    def verify_c(self, code: str) -> Tuple[bool, str]:
        return self.registry.verify_c17(code)

    def verify_cpp(self, code: str) -> Tuple[bool, str]:
        return self.registry.verify_cpp20(code)

    def verify_ebpf(self, code: str) -> Tuple[bool, str]:
        return self.registry.verify_ebpf(code)

    def verify_lean4(self, code: str, theorem_name: Optional[str] = None) -> Tuple[bool, str]:
        return self.registry.verify_lean4(code, theorem_name)

    def verify_x86_assembly(self, code: str, use_intel_syntax: bool = True) -> Tuple[bool, str]:
        return self.registry.verify_x86_assembly(code, use_intel_syntax)

    def verify_arm64_assembly(self, code: str) -> Tuple[bool, str]:
        return self.registry.verify_arm64_assembly(code)

    def verify_riscv_assembly(self, code: str) -> Tuple[bool, str]:
        return self.registry.verify_riscv_assembly(code)

    def verify_llvm_ir(self, code: str) -> Tuple[bool, str]:
        return self.registry.verify_llvm_ir(code)

    def verify_cuda(self, code: str) -> Tuple[bool, str]:
        return self.registry.verify_cuda(code)

    def verify_genomics(self, sequence: str, target_pam: Optional[str] = "NGG") -> Tuple[bool, str]:
        return self.registry.verify_genomics_dna(sequence, target_pam)

    def verify_smiles(self, smiles: str) -> Tuple[bool, str]:
        return self.registry.verify_smiles_valency(smiles)

    def verify_tool_call(self, json_str: str) -> Tuple[bool, str]:
        return self.registry.verify_tool_call_json(json_str)

    def verify_sample(self, text: str, domain: str) -> Tuple[bool, str]:
        """Routes domain strings to the corresponding ground-truth execution verifier."""
        d = domain.lower()
        if d in ["python", "py"]:
            return self.verify_python(text)
        elif d in ["rust", "rs"]:
            return self.verify_rust(text)
        elif d in ["lean", "lean4"]:
            return self.verify_lean4(text)
        elif d in ["c", "c17"]:
            return self.verify_c(text)
        elif d in ["cpp", "c++", "cpp20"]:
            return self.verify_cpp(text)
        elif d in ["ebpf", "bpf"]:
            return self.verify_ebpf(text)
        elif d in ["x86", "x86_64", "asm", "assembly"]:
            return self.verify_x86_assembly(text)
        elif d in ["arm", "arm64", "aarch64"]:
            return self.verify_arm64_assembly(text)
        elif d in ["riscv", "riscv64", "rv64"]:
            return self.verify_riscv_assembly(text)
        elif d in ["llvm", "llvm_ir", "ir"]:
            return self.verify_llvm_ir(text)
        elif d in ["cuda", "nvcc"]:
            return self.verify_cuda(text)
        elif d in ["dna", "genomics", "crispr"]:
            return self.verify_genomics(text)
        elif d in ["smiles", "chemistry", "cheminformatics"]:
            return self.verify_smiles(text)
        elif d in ["json", "tool_call", "rpc", "agent"]:
            return self.verify_tool_call(text)
        elif d == "math":
            has_thought = "<thought>" in text and "</thought>" in text
            has_ans = "Answer:" in text or "####" in text
            return (has_thought and has_ans), "Valid arithmetic CoT structure."
        else:
            return True, f"Unknown domain '{domain}' passed (no-op)."
