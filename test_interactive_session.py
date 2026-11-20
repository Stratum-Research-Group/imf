"""
End-to-End Comprehensive Multi-Domain Interactive Verification Harness.
Feeds complete, multi-line blocks across all 10 systems and scientific modes into
the IMF Ground-Truth Execution Verifiers and reports detailed pass diagnostics.
"""

from imf.execution_verifier import MultiLanguageExecutionVerifier
from imf.scientific_execution_verifiers import ScientificExecutionVerifier


def run_comprehensive_interactive_session():
    print("=" * 80)
    print("  IMF MULTI-DOMAIN LIVE VERIFICATION SESSION (v0.8.0)")
    print("  Evaluating Compilers: C17, Linux eBPF, Rust, Python, Lean 4")
    print("  Evaluating Sciences : CRISPR, SMILES Chemistry, Quantum Pure State, ORF")
    print("=" * 80)

    v = MultiLanguageExecutionVerifier()
    sv = ScientificExecutionVerifier()

    test_battery = [
        ("C17 (GCC/Clang)", "c",
         ("int calculate_crc32(const char *buf, int len) {\n"
          "    int crc = (int)0xFFFFFFFF;\n"
          "    for (int i = 0; i < len; i++) { crc ^= (int)buf[i]; }\n"
          "    return crc;\n"
          "}\n")),

        ("Linux eBPF (Clang -target bpf)", "ebpf",
         ("int kprobe__sys_clone(void *ctx) {\n"
          "    (void)ctx;\n"
          "    return 0;\n"
          "}\n")),

        ("Rust (rustc lib crate)", "rust",
         ("pub fn compute_dot_product(a: &[f32], b: &[f32]) -> f32 {\n"
          "    a.iter().zip(b.iter()).map(|(x, y)| x * y).sum()\n"
          "}\n")),

        ("Python 3.12+ AST", "python",
         ("def dijkstra_heap(adj: dict[int, list[tuple[int, int]]], src: int) -> dict[int, int]:\n"
          "    import heapq\n"
          "    dist = {k: float('inf') for k in adj}\n"
          "    dist[src] = 0\n"
          "    return {k: int(v) for k, v in dist.items()}\n")),

        ("Lean 4 Formal Proof Tactic", "lean4",
         ("theorem nat_add_zero_refl (n : Nat) : n + 0 = n := by\n"
          "  exact Nat.add_zero n\n")),

        ("CRISPR-Cas9 20nt + PAM", "crispr",
         "GAGTTCTTGCTCTTCATCGATGG"),

        ("Chemistry SMILES Valency", "smiles",
         "CC(=O)Oc1ccccc1C(=O)O"),

        ("Quantum State Vector (Bell State)", "quantum",
         [0.70710678 + 0j, 0j, 0j, 0.70710678 + 0j]),

        ("Genomics ORF Translation", "orf",
         "ATGGCCAAGTTTTAA")
    ]

    results = []
    for label, mode, payload in test_battery:
        print(f"\n[>] Testing Domain: {label}...")
        if mode == "c":
            passed, diag = v.verify_c(payload)
        elif mode == "ebpf":
            passed, diag = v.verify_ebpf(payload)
        elif mode == "rust":
            passed, diag = v.verify_rust(payload)
        elif mode == "python":
            passed, diag = v.verify_python(payload)
        elif mode == "lean4":
            passed, diag = v.verify_lean4(payload)
        elif mode == "crispr":
            passed, diag = sv.verify_crispr_pam(payload)
        elif mode == "smiles":
            passed, diag = sv.verify_smiles_grammar(payload)
        elif mode == "quantum":
            passed, diag = sv.verify_quantum_state(payload)
        elif mode == "orf":
            passed, diag = sv.verify_orf_translation(payload)
        else:
            passed, diag = False, "Unknown mode"

        status_str = "[✓ PASS]" if passed else "[✗ FAIL]"
        print(f"    Status: {status_str} | Diagnostic: {diag}")
        results.append((label, passed, diag))

    print("\n" + "=" * 80)
    print("  SUMMARY: MULTI-DOMAIN VERIFICATION BATTERY")
    print("=" * 80)
    for label, passed, diag in results:
        sym = "PASS" if passed else "FAIL"
        print(f"  {label:<35} | {sym:<6} | {diag[:40]}...")
    print("=" * 80)
    all_ok = all(r[1] for r in results)
    print(f"[+] All Domains Verified Deterministically: {all_ok}")


if __name__ == "__main__":
    run_comprehensive_interactive_session()
