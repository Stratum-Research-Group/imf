"""
Interactive Agentic Self-Correction Terminal REPL (IMF).
Bridges IMF autoregressive candidate generation with real system compilers:
- :py   -> Python 3.12 AST & Bytecode Compilation
- :rs   -> Rustc crate library syntax & borrow-check verification
- :lean -> Lean 4 formal tactic & proof closure verification
- :ps   -> PowerShell / Windows Script syntax check
- :sh   -> Bash POSIX AST parser

When an error is detected, the Agentic Self-Correction Loop absorbs the compiler
diagnostic in <turn:tool_response> and autonomously repairs the candidate.
"""

import sys
from imf.execution_verifier import MultiLanguageExecutionVerifier
from imf.scientific_execution_verifiers import ScientificExecutionVerifier
from imf.agentic_self_correction_loop import AgenticSelfCorrectionEngine

def main():
    verifier = MultiLanguageExecutionVerifier()
    sci_verifier = ScientificExecutionVerifier()
    engine = AgenticSelfCorrectionEngine()

    print("=" * 75)
    print("  IMF AGENTIC SELF-CORRECTION COMPILER & SCIENCE REPL (v0.8.0)")
    print("  Compilers: :py, :rs, :c, :bpf, :lean")
    print("  Sciences : :dna, :crispr, :orf, :smi, :quant, :quit")
    print("=" * 75)

    mode = "python"
    while True:
        try:
            line = input(f"imf-repl [{mode}]> ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting REPL.")
            break

        line_strip = line.strip()
        if not line_strip:
            continue
        if line_strip == ":quit" or line_strip == ":exit":
            print("Goodbye.")
            break
        elif line_strip == ":py":
            mode = "python"; print("[*] Switched to Python AST verifier mode."); continue
        elif line_strip == ":rs":
            mode = "rust"; print("[*] Switched to Rustc verifier mode."); continue
        elif line_strip == ":c":
            mode = "c"; print("[*] Switched to C17 (GCC/Clang) verifier mode."); continue
        elif line_strip == ":bpf":
            mode = "ebpf"; print("[*] Switched to Linux eBPF (Clang -target bpf) verifier mode."); continue
        elif line_strip == ":lean":
            mode = "lean4"; print("[*] Switched to Lean 4 tactic verifier mode."); continue
        elif line_strip == ":dna":
            mode = "dna"; print("[*] Switched to DNA FASTA nucleotide verifier mode."); continue
        elif line_strip == ":crispr":
            mode = "crispr"; print("[*] Switched to CRISPR SpCas9 PAM verifier mode."); continue
        elif line_strip == ":orf":
            mode = "orf"; print("[*] Switched to Open Reading Frame (ORF) verifier mode."); continue
        elif line_strip == ":smi":
            mode = "smiles"; print("[*] Switched to SMILES chemical valency verifier mode."); continue
        elif line_strip == ":quant":
            mode = "quantum"; print("[*] Switched to Quantum state normalization verifier mode."); continue

        code = line
        print(f"[*] Dispatching to {mode} verifier...")

        passed, diag = False, "Unknown mode"
        if mode == "python":
            passed, diag = verifier.verify_python(code)
        elif mode == "rust":
            passed, diag = verifier.verify_rust(code)
        elif mode == "c":
            passed, diag = verifier.verify_c(code)
        elif mode == "ebpf":
            passed, diag = verifier.verify_ebpf(code)
        elif mode == "lean4":
            passed, diag = verifier.verify_lean4(code)
        elif mode == "dna":
            passed, diag = sci_verifier.verify_dna_fasta(code)
        elif mode == "crispr":
            passed, diag = sci_verifier.verify_crispr_pam(code)
        elif mode == "orf":
            passed, diag = sci_verifier.verify_orf_translation(code)
        elif mode == "smiles":
            passed, diag = sci_verifier.verify_smiles_grammar(code)
        elif mode == "quantum":
            try:
                import ast
                amps = [complex(x) for x in ast.literal_eval(code)]
                passed, diag = sci_verifier.verify_quantum_state(amps)
            except Exception as e:
                passed, diag = False, f"Invalid complex state array: {e}"

        if passed:
            print(f"[✓ PASS] Verification Succeeded:\n    {diag}")
        else:
            print(f"[✗ FAIL] Diagnostic:\n    {diag}")

        if passed:
            print(f"[✓ PASS] Compiler Verification Succeeded:\n    {diag}")
        else:
            print(f"[✗ FAIL] Compiler Diagnostic:\n    {diag}")
            print("[*] Triggering Test-Time Agentic Self-Correction Engine...")
            
            # Multi-Turn Agentic Self-Correction Loop via MCTS Cut-Search
            from imf.frontier_mcts_cut_engine import FrontierMCTSCutEngine
            engine = FrontierMCTSCutEngine(branching_factor=4, max_depth=6)

            res = engine.bidirectional_cut_search(
                premise=code,
                goal="",
                lang=mode,
                num_simulations=16
            )
            repaired = res.get("solution", code)
            
            if mode == "python":
                rep_pass, rep_diag = verifier.verify_python(repaired)
            elif mode == "rust":
                rep_pass, rep_diag = verifier.verify_rust(repaired)
            elif mode == "lean4":
                rep_pass, rep_diag = verifier.verify_lean4(repaired)
            elif mode in ("c", "c17"):
                rep_pass, rep_diag = verifier.verify_c(repaired)
            elif mode == "ebpf":
                rep_pass, rep_diag = verifier.verify_ebpf(repaired)
            else:
                rep_pass, rep_diag = False, "Unknown domain for self-correction"

            if rep_pass:
                print(f"[✓ REPAIRED] Autonomous Self-Correction Succeeded:\n{repaired}\n    {rep_diag}")
            else:
                print(f"[!] Requires further AST synthesis: {rep_diag}")

if __name__ == "__main__":
    main()
