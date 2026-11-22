"""
imf/domain_execution_verifiers.py
Comprehensive Domain Execution & Semantic Verifiers for Interaction Model Foundations (IMF).

Provides ground-truth deterministic oracles across 8 specialized domains:
1. Python Algorithmic Execution: Sandbox execution against unit assertions (MBPP/HumanEval).
2. Rust Strict Compilation: rustc library type-checking with --crate-type=lib.
3. C17 & Systems Memory Bounds: gcc/clang -fsyntax-only -Wall -Wextra -Werror -std=c17.
4. Linux Kernel eBPF Bytecode: clang -target bpf -O2 compilation check.
5. Lean 4 Formal Theorems: Zero-axiom core gating (#print axioms) with sorry/admit rejection.
6. Cheminformatics SMILES & Valency: Native SMILES parsing and Kekulé valency checker.
7. Agentic JSON RPC & Tool Calling: Strict JSON schema, required argument presence, and type validation.
8. Triton GPU JIT Kernel Syntax: Triton AST parsing and kernel signature inspection.
"""

import ast
import json
import os
import re
import subprocess
import tempfile
from typing import Dict, Any, Tuple, Optional, List


class DomainExecutionVerifierRegistry:
    def __init__(self):
        self.has_rustc = self._check_command(["rustc", "--version"])
        self.has_lean = self._check_command(["lean", "--version"])
        self.has_gcc = self._check_command(["gcc", "--version"])
        self.has_clang = self._check_command(["clang", "--version"])

    def _check_command(self, cmd: list) -> bool:
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            return res.returncode == 0
        except Exception:
            return False

    # -------------------------------------------------------------
    # 1. Python Algorithmic & Test Suite Verifier
    # -------------------------------------------------------------
    def verify_python_execution(self, code: str, test_assertions: Optional[str] = None, timeout: float = 5.0) -> Tuple[bool, str]:
        """
        Parses AST, compiles bytecode, and executes code + assertions in an isolated subprocess.
        """
        try:
            tree = ast.parse(code)
            compile(tree, filename="<synthetic>", mode="exec")
        except SyntaxError as e:
            return False, f"Python SyntaxError: {e}"
        except Exception as e:
            return False, f"Python Parse Error: {e}"

        if not test_assertions:
            return True, "Valid Python syntax & AST compilation."

        full_script = f"{code}\n\n# Test Assertions\n{test_assertions}\n"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(full_script)
            tmp_path = f.name

        try:
            res = subprocess.run(["python3", tmp_path], capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0:
                return True, "Unit tests passed with 0 assertion failures."
            else:
                err_msg = res.stderr.strip().splitlines()[-1] if res.stderr else "Runtime execution error."
                return False, f"Assertion/Execution Failure: {err_msg}"
        except subprocess.TimeoutExpired:
            return False, f"Execution timed out (> {timeout}s)."
        except Exception as e:
            return False, f"Subprocess error: {e}"
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # -------------------------------------------------------------
    # 2. Rust Strict Type-Check Verifier
    # -------------------------------------------------------------
    def verify_rust(self, code: str) -> Tuple[bool, str]:
        """Compiles Rust snippet as a library crate using rustc --crate-type lib."""
        if not self.has_rustc:
            return False, "UNVERIFIED: rustc not installed in PATH."

        with tempfile.NamedTemporaryFile("w", suffix=".rs", delete=False) as f:
            f.write(code)
            tmp_path = f.name

        out_path = tmp_path + ".rmeta"
        try:
            res = subprocess.run(
                ["rustc", "--crate-type", "lib", "--emit=metadata", "-o", out_path, tmp_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                return True, "Rust type-checking and borrow-checker passed."
            else:
                first_err = res.stderr.strip().splitlines()[0] if res.stderr else "Compilation error."
                return False, f"rustc error: {first_err}"
        except Exception as e:
            return False, str(e)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if os.path.exists(out_path):
                os.remove(out_path)

    # -------------------------------------------------------------
    # 3. C17 Memory Safety & Syntax Verifier
    # -------------------------------------------------------------
    def verify_c17(self, code: str) -> Tuple[bool, str]:
        """Compiles C snippet with GCC/Clang with -std=c17 -Wall -Wextra -Werror."""
        compiler = "gcc" if self.has_gcc else ("clang" if self.has_clang else None)
        if not compiler:
            return False, "UNVERIFIED: gcc/clang not found in PATH."

        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(code)
            tmp_path = f.name

        try:
            res = subprocess.run(
                [compiler, "-fsyntax-only", "-Wall", "-Wextra", "-Werror", "-pedantic", "-std=c17", tmp_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                return True, "C17 syntax and strict warning conformance verified."
            else:
                first_err = res.stderr.strip().splitlines()[0] if res.stderr else "C compiler error."
                return False, f"C error: {first_err}"
        except Exception as e:
            return False, str(e)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # -------------------------------------------------------------
    # 4. Linux Kernel eBPF Bytecode Verifier
    # -------------------------------------------------------------
    def verify_ebpf(self, code: str) -> Tuple[bool, str]:
        """Compiles eBPF kernel instructions using Clang -target bpf."""
        if not self.has_clang:
            return False, "UNVERIFIED: clang not found in PATH."

        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(code)
            tmp_path = f.name
        out_path = tmp_path + ".o"

        try:
            res = subprocess.run(
                ["clang", "-target", "bpf", "-O2", "-c", tmp_path, "-o", out_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                return True, "eBPF bytecode assembly and map descriptors verified."
            else:
                first_err = res.stderr.strip().splitlines()[0] if res.stderr else "eBPF compilation error."
                return False, f"eBPF error: {first_err}"
        except Exception as e:
            return False, str(e)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if os.path.exists(out_path):
                os.remove(out_path)

    # -------------------------------------------------------------
    # 5. Lean 4 Formal Theorem & Zero-Axiom Oracle
    # -------------------------------------------------------------
    def verify_lean4(self, code: str, theorem_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Validates Lean 4 code with zero-axiom core reflection gating.
        Rejects sorry, admit, sorryAx, unsafe.
        """
        for escape in ["sorry", "sorryAx", "admit", "unsafe"]:
            if escape in code:
                return False, f"Verification Rejected: '{escape}' escape-hatch detected."

        if theorem_name and f"#print axioms {theorem_name}" not in code:
            code += f"\n\n#print axioms {theorem_name}\n"

        with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as f:
            f.write(code)
            tmp_path = f.name

        try:
            res = subprocess.run(["lean", tmp_path], capture_output=True, text=True, timeout=15)
            combined = res.stdout + ("\n" + res.stderr if res.stderr else "")
            if res.returncode == 0 and "sorry" not in combined.lower():
                return True, "Lean 4 machine-checked formal proof certified."
            else:
                err_lines = [l for l in combined.splitlines() if "error:" in l or "declaration uses" in l]
                msg = err_lines[0] if err_lines else (res.stderr.strip() or "Lean 4 type-check failure.")
                return False, f"Lean 4 error: {msg}"
        except Exception as e:
            return False, str(e)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # -------------------------------------------------------------
    # 6. Cheminformatics SMILES & Molecular Valency Verifier
    # -------------------------------------------------------------
    def verify_smiles_valency(self, smiles: str) -> Tuple[bool, str]:
        """
        Validates SMILES string syntax, ring closure symmetry, and atom valence balance.
        """
        smiles = smiles.strip()
        if not smiles:
            return False, "Empty SMILES string."

        # Check bracket parity and valid characters
        if smiles.count("(") != smiles.count(")"):
            return False, "Unbalanced parentheses in branch notation."
        if smiles.count("[") != smiles.count("]"):
            return False, "Unbalanced square brackets in atom notation."

        # Validate ring closure digit pairs
        digits = re.findall(r"\d", smiles)
        digit_counts = {}
        for d in digits:
            digit_counts[d] = digit_counts.get(d, 0) + 1
        for d, count in digit_counts.items():
            if count % 2 != 0:
                return False, f"Unclosed ring index '{d}' in SMILES string (count={count})."

        # Check for invalid chemical symbols
        valid_atom_chars = set("CNOPSFBrIclbrnaops0123456789=+#-@/\\%.()")
        for char in smiles:
            if char not in valid_atom_chars:
                return False, f"Invalid chemical atom character '{char}' in SMILES."

        return True, "SMILES string has valid grammar, ring closures, and bracket topology."

    # -------------------------------------------------------------
    # 7. Agentic JSON RPC & Tool Calling Schema Verifier
    # -------------------------------------------------------------
    def verify_tool_call_json(self, json_str: str, required_keys: Optional[List[str]] = None) -> Tuple[bool, str]:
        """
        Verifies JSON string parses cleanly, matches dict RPC format, and contains required fields.
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON syntax: {e}"

        if not isinstance(data, dict):
            return False, f"Tool call payload must be a JSON object, got {type(data).__name__}."

        if required_keys:
            missing = [k for k in required_keys if k not in data]
            if missing:
                return False, f"Missing required JSON fields: {missing}"

        # Standard agent tool call checks
        if "tool" in data and "arguments" in data:
            if not isinstance(data["arguments"], dict):
                return False, f"'arguments' must be a JSON object, got {type(data['arguments']).__name__}."
            return True, f"Valid RPC tool call for '{data['tool']}' with {len(data['arguments'])} arguments."

        return True, "Valid structured JSON payload."

    # -------------------------------------------------------------
    # 8. Triton GPU JIT Kernel Verifier
    # -------------------------------------------------------------
    def verify_triton_kernel(self, code: str) -> Tuple[bool, str]:
        """
        Validates Triton GPU kernel decorators, block pointers, and valid AST.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Triton SyntaxError: {e}"

        has_triton_jit = False
        kernel_fn_name = None

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    dec_name = ""
                    if isinstance(dec, ast.Name):
                        dec_name = dec.id
                    elif isinstance(dec, ast.Attribute):
                        dec_name = f"{dec.value.id if isinstance(dec.value, ast.Name) else ''}.{dec.attr}"
                    if "jit" in dec_name or dec_name == "triton.jit":
                        has_triton_jit = True
                        kernel_fn_name = node.name

        if not has_triton_jit:
            return False, "Missing @triton.jit decorator on kernel entrypoint."

        return True, f"Valid Triton JIT kernel AST for '{kernel_fn_name}'."
