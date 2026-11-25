"""
scripts/run_and_record_tests.py
Executes the test suite and generates benchmark_results/test_summary.json
with exact passed, failed, and skipped counts.
"""

import sys
import json
import time
import subprocess
from pathlib import Path

def main():
    print("=" * 80)
    print("  IMF AUTOMATED TEST RUNNER & BENCHMARK SUMMARY RECORDER")
    print("=" * 80)

    out_dir = Path("benchmark_results")
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "test_summary.json"

    t0 = time.perf_counter()
    res = subprocess.run(
        ["pytest", "--junitxml=benchmark_results/junit.xml", "-q"],
        capture_output=True,
        text=True
    )
    elapsed = time.perf_counter() - t0

    # Parse pytest output
    stdout = res.stdout + "\n" + res.stderr
    print(stdout)

    # Simple parsing of final summary line (e.g., "111 passed, 1 warning in 12.34s")
    passed = 0
    failed = 0
    skipped = 0

    import xml.etree.ElementTree as ET
    xml_path = out_dir / "junit.xml"
    if xml_path.exists():
        tree = ET.parse(xml_path)
        root = tree.getroot()
        testsuite = root.find("testsuite") or root
        tests = int(testsuite.attrib.get("tests", 0))
        failures = int(testsuite.attrib.get("failures", 0))
        errors = int(testsuite.attrib.get("errors", 0))
        skipped = int(testsuite.attrib.get("skipped", 0))
        failed = failures + errors
        passed = tests - failed - skipped
    else:
        # Fallback regex
        pass

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "return_code": res.returncode,
        "elapsed_seconds": round(elapsed, 2),
        "total_tests": passed + failed + skipped,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "hardware": "AMD Ryzen 5 7600X | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB)"
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=" * 80)
    print(f"[✓] Test Summary written to {summary_path}")
    print(f"    Passed: {passed} | Failed: {failed} | Skipped: {skipped} | Duration: {elapsed:.2f}s")
    print("=" * 80)

    return res.returncode

if __name__ == "__main__":
    sys.exit(main())
