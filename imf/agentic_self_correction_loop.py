"""
Test-Time Compute Scaling & Self-Correction Agent Loop (IMF).
Executes code generation with compiler feedback (Python AST, rustc, Lean 4).
If a compiler rejects candidate code, the agent ingests the error diagnostics in
<turn:tool_response>, reflects in <thought>, and produces a verified correction.
"""

from typing import Dict, Any, Tuple
from imf.execution_verifier import MultiLanguageExecutionVerifier


class AgenticSelfCorrectionEngine:
    def __init__(self):
        self.verifier = MultiLanguageExecutionVerifier()

    def run_correction_cycle(self, lang: str, initial_code: str, corrected_code: str) -> Dict[str, Any]:
        """
        Simulates a multi-turn self-correction trajectory:
        1. Verifier tests initial code -> yields error diagnostic.
        2. Agent receives diagnostic in <turn:tool_response>.
        3. Agent reflects and generates corrected_code.
        4. Verifier confirms closure.
        """
        # Step 1: Initial verification
        if lang == "python":
            pass1, err1 = self.verifier.verify_python(initial_code)
            pass2, err2 = self.verifier.verify_python(corrected_code)
        elif lang == "rust":
            pass1, err1 = self.verifier.verify_rust(initial_code)
            pass2, err2 = self.verifier.verify_rust(corrected_code)
        elif lang == "lean4":
            pass1, err1 = self.verifier.verify_lean4(initial_code)
            pass2, err2 = self.verifier.verify_lean4(corrected_code)
        else:
            raise ValueError(f"Unsupported language: {lang}")

        trajectory = (
            f"<turn:user>\nImplement a verified {lang} function.\n</turn:user>\n"
            f"<turn:assistant>\n"
            f"<thought>Proposing initial candidate implementation.</thought>\n"
            f"```{lang}\n{initial_code.strip()}\n```\n"
            f"</turn:assistant>\n"
            f"<turn:tool_response>\n[Compiler Feedback: success={pass1}, diagnostic='{err1.strip()}']\n</turn:tool_response>\n"
            f"<turn:assistant>\n"
            f"<thought>Compiler diagnostic indicates syntax/type failure: {err1.strip()}. Applying AST-preserving repair.</thought>\n"
            f"```{lang}\n{corrected_code.strip()}\n```\n"
            f"</turn:assistant>\n"
            f"<turn:tool_response>\n[Compiler Feedback: success={pass2}, diagnostic='{err2.strip()}']\n</turn:tool_response>"
        )

        return {
            "lang": lang,
            "initial_success": pass1,
            "corrected_success": pass2,
            "recovered": (not pass1 and pass2),
            "trajectory": trajectory
        }


if __name__ == "__main__":
    engine = AgenticSelfCorrectionEngine()
    
    # Test 1: Python syntax repair
    bad_py = "def broken(x: int -> int: return x + 1"
    good_py = "def fixed(x: int) -> int:\n    return x + 1\n"
    res_py = engine.run_correction_cycle("python", bad_py, good_py)
    print(f"[*] Python Self-Correction Recovery: {res_py['recovered']}")
    assert res_py["recovered"]

    # Test 2: Lean 4 proof closure repair
    bad_lean = "theorem bad (n : Nat) : n + 0 = n := by\n  sorry\n"
    good_lean = "theorem good (n : Nat) : n + 0 = n := by\n  exact Nat.add_zero n\n"
    res_lean = engine.run_correction_cycle("lean4", bad_lean, good_lean)
    print(f"[*] Lean 4 Self-Correction Recovery: {res_lean['recovered']}")
    assert res_lean["recovered"]
    
    print("[+] Agentic Self-Correction verification loop verified successfully.")
