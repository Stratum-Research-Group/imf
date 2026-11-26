"""
scripts/run_all_benchmarks.py
Consolidated End-to-End Release Test Suite for Interaction Model Foundations (IMF):
Executes and aggregates all core empirical and formal verification gates:
1. Directional Recall & Phase Margin Separation (test_savg_directionality.py)
2. Factual Reversal Curse Resolution (benchmark_reversal_curse.py)
3. Long-Context MQAR Sub-Quadratic Scaling up to 4096 (benchmark_long_context_mqar.py)
4. Needle-In-A-Haystack (NIAH) 16k Full Grid Retrieval (benchmark_needle_in_haystack.py)
5. Polytope Landmark Simplex & Orthoplex Ablation (benchmark_polytope_ablation.py)
6. Unit Test Regression Suite (pytest tests/)
7. Interactive Lean 4 Formal Verification Build (lake build)

Generates an aggregated Markdown execution report: docs/reports/IMF_VERIFICATION_REPORT.md
"""

import sys
import os
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = DOCS_DIR / "IMF_VERIFICATION_REPORT.md"


def run_cmd(name: str, cmd: list[str], cwd: Path = ROOT) -> tuple[int, str, float]:
    print(f"\n[>] Running: {name} ({' '.join(cmd)})...")
    t0 = time.perf_counter()
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    dt = time.perf_counter() - t0
    status_str = "PASS [✓]" if res.returncode == 0 else "FAIL [✗]"
    print(f"    Status: {status_str} in {dt:.2f}s")
    return res.returncode, res.stdout + "\n" + res.stderr, dt


def main():
    print("=" * 90)
    print("INTERACTION MODEL FOUNDATIONS (IMF) — FULL RELEASE VERIFICATION SUITE")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)

    py_bin = str(ROOT / ".venv" / "bin" / "python")
    elan_bin = os.path.expanduser("~/.elan/bin")
    env_path = f"{elan_bin}:{os.environ.get('PATH', '')}"

    gates = [
        ("Unit Test Regression Suite", [py_bin, "-m", "pytest", "tests/"]),
        ("Directional Recall & Phase Margin Test", [py_bin, "test_savg_directionality.py"]),
        ("Factual Reversal Curse Benchmark", [py_bin, "benchmark_reversal_curse.py"]),
        ("Chiral Enantiomer Discrimination Benchmark", [py_bin, "benchmark_chiral_discrimination.py"]),
        ("Extreme Multilinear Arity Benchmark", [py_bin, "benchmark_infinite_arity_scaling.py"]),
        ("Long-Context Sub-Quadratic MQAR Scaling", [py_bin, "benchmark_long_context_mqar.py"]),
        ("Needle-In-A-Haystack 8k Retrieval", [py_bin, "benchmark_needle_in_haystack.py"]),
        ("Polytope Geometric Ablation Benchmark", [py_bin, "benchmark_polytope_ablation.py"]),
        ("Polytope Barycentric Sparsity Dynamics", [py_bin, "visualize_polytope_sparsity.py"]),
    ]

    results = []
    total_t0 = time.perf_counter()

    for name, cmd in gates:
        rc, out, dt = run_cmd(name, cmd)
        results.append({
            "name": name,
            "cmd": " ".join(cmd),
            "rc": rc,
            "dt": dt,
            "output": out
        })

    # Run Lean 4 proofs
    lean_cmd = ["lake", "build"]
    print(f"\n[>] Running: Formal Lean 4 Verification (lake build)...")
    t0 = time.perf_counter()
    lean_res = subprocess.run(
        lean_cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": env_path}
    )
    lean_dt = time.perf_counter() - t0
    lean_status = "PASS [✓]" if lean_res.returncode == 0 else "FAIL [✗]"
    print(f"    Status: {lean_status} in {lean_dt:.2f}s")
    results.append({
        "name": "Formal Lean 4 Proof Verification",
        "cmd": "lake build",
        "rc": lean_res.returncode,
        "dt": lean_dt,
        "output": lean_res.stdout + "\n" + lean_res.stderr
    })

    total_time = time.perf_counter() - total_t0

    # Build Markdown Report
    passed_count = sum(1 for r in results if r["rc"] == 0)
    total_count = len(results)
    verdict = "VERIFIED — ALL GATES PASSED (PRODUCTION READY)" if passed_count == total_count else "FAILED GATES DETECTED"

    report_lines = [
        "# IMF Comprehensive Release Verification Report",
        "",
        f"- **Date / Time**: `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
        f"- **Verdict**: **{verdict}**",
        f"- **Passing Gates**: `{passed_count}/{total_count}`",
        f"- **Total Test Duration**: `{total_time:.2f} seconds`",
        "",
        "---",
        "",
        "## Summary Table",
        "",
        "| Gate / Benchmark | Command | Status | Duration |",
        "| :--- | :--- | :---: | :---: |",
    ]

    for r in results:
        status_md = "PASS [✓]" if r["rc"] == 0 else "FAIL [✗]"
        report_lines.append(f"| **{r['name']}** | `{r['cmd']}` | `{status_md}` | `{r['dt']:.2f}s` |")

    report_lines.extend([
        "",
        "---",
        "",
        "## Detailed Gate Outputs",
        "",
    ])

    for r in results:
        report_lines.extend([
            f"### {r['name']}",
            f"- **Status**: `{'PASS' if r['rc'] == 0 else 'FAIL'}` (Exit Code `{r['rc']}`)",
            f"- **Duration**: `{r['dt']:.2f}s`",
            "```text",
            r["output"].strip()[-2500:] if len(r["output"].strip()) > 2500 else r["output"].strip(),
            "```",
            "",
        ])

    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\n[✓] Aggregated verification report written to: {REPORT_PATH}")

    if passed_count != total_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
