import sys

md_path = 'docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.md'

with open(md_path, 'r', encoding='utf-8') as f:
    text = f.read()

# -------------------------------------------------------------
# Item 5: Explicit Disclaimer Header
# -------------------------------------------------------------
old_header = """**Series:** The Sacred Sanctum: Foundations of Sovereign Intelligence (IMF Magnum Opus Trilogy)  
**Author:** Nicholas Charles Mynhardt  
**Organization:** Stratum Research Group (SRG)  
**Date:** November 27, 2026  
**Status:** Research Monograph (Preprint / Internal Research Distribution)  
**Formally Verified Modules:** Lean 4 Mathlib Pilots (Standard CIC Foundations, 0 `sorry`)  
**Hardware Baseline:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti 16GB GDDR7 (Blackwell SM 12.0)  
**OS Baseline:** Omarchy Linux (Kernel 7.2.15-1-omarchy) with PREEMPT_RT and liburing  """

new_header = """**Series:** The Sacred Sanctum: Foundations of Sovereign Intelligence (IMF Magnum Opus Trilogy)  
**Author:** Nicholas Charles Mynhardt  
**Organization:** Stratum Research Group (SRG)  
**Date:** November 27, 2026  
**Status:** Preprint, not independently reviewed  
**Formal Verification:** Algebraic pilot specifications under Lean 4 Mathlib (no `sorry`, standard CIC axioms only)  
**Hardware Baseline:** Single-machine physical evaluation (AMD Ryzen 5 7600X, NVIDIA GeForce RTX 5060 Ti 16GB GDDR7, Blackwell SM 12.0)  
**OS Baseline:** Omarchy Linux (Kernel 7.2.15-1-omarchy) with PREEMPT_RT and liburing  """

assert old_header in text, "old_header not found"
text = text.replace(old_header, new_header, 1)

# -------------------------------------------------------------
# Item 4: Axioms phrasing in text ("no sorry, standard axioms only")
# -------------------------------------------------------------
text = text.replace("0 `sorry` and 0 unproven axioms", "no `sorry`, standard CIC axioms only")
text = text.replace("with strictly 0 unproven axioms (`0 sorry`)", "with no `sorry` using standard CIC axioms only")

# -------------------------------------------------------------
# Update Table 8.1 with Bidirectional MQAR and ncu profile
# -------------------------------------------------------------
old_ledger_row = """|                                    | Precision Drift (1,000 steps)    | FP32: 2.8e-6, FP16: 0.46%, BF16: 4.1% |
|                                    | Param-Matched MQAR (N=8)         | Trans: 100%, Mamba2: 100%, IMF: 26% |"""

new_ledger_row = """|                                    | Precision Drift (1,000 steps)    | FP32: 2.8e-6, FP16: 0.46%, BF16: 4.1% |
|                                    | Param-Matched MQAR (N=8)         | Trans: 100%, Mamba2: 100%, IMF: 26% |
|                                    | Bidirectional SAVG MQAR (N=8)    | Forward: 100.0%, Reverse: 100.0%    |
|                                    | Silicon ALU Time (ncu)           | 280.1 ns (lie_kv_ncu_profile.txt)   |
|                                    | 3D Simplicial DEC Nilpotency     | d1 * d0 = 0 (test_dec_3d_complex)   |"""

assert old_ledger_row in text, "old_ledger_row not found"
text = text.replace(old_ledger_row, new_ledger_row, 1)

with open(md_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated Vol 1 header and Table 8.1 with full review resolutions!")
