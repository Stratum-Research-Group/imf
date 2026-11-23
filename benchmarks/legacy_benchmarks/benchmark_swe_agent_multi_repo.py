"""
benchmark_swe_agent_multi_repo.py
Evaluates MultiFileSWEAgent against a multi-module repository benchmark
with injected defects across multiple coupled files.

Tracks:
1. Multi-file trace diagnosis accuracy.
2. AST patch localization and repair.
3. Multi-turn regression closure rate.
"""

import sys
import time

from imf.multi_file_swe_agent import MultiFileSWEAgent


BENCHMARK_SCENARIOS = [
    {
        "name": "Scenario 1: Multi-Module Arithmetic Subtraction Bug",
        "description": "calc.py has an erroneous Subtraction node; consumer app.py and tests fail",
        "project_files": {
            "calc.py": "def add_elements(a, b):\n    return a - b\n",
            "app.py": "from calc import add_elements\n\ndef run():\n    return add_elements(10, 5)\n",
        },
        "test_file": "tests/test_calc.py",
        "test_code": "from app import run\n\nassert run() == 15, f'Expected 15, got {run()}'\nprint('TEST PASSED')\n",
    },
    {
        "name": "Scenario 2: Relational Inversion Bug Across Modules",
        "description": "validator.py uses != instead of ==; engine.py and assertions fail",
        "project_files": {
            "validator.py": "def is_valid_token(tok, target):\n    return tok != target\n",
            "engine.py": "from validator import is_valid_token\n\ndef process(tok):\n    if is_valid_token(tok, 'AUTH_KEY'):\n        return 'GRANTED'\n    return 'DENIED'\n",
        },
        "test_file": "tests/test_auth.py",
        "test_code": "from engine import process\n\nassert process('AUTH_KEY') == 'GRANTED'\nassert process('WRONG') == 'DENIED'\nprint('AUTH TEST PASSED')\n",
    },
    {
        "name": "Scenario 3: Multi-Layer Coordinate Difference Inversion",
        "description": "geometry.py computes difference; pipeline.py requires additive accumulation",
        "project_files": {
            "geometry.py": "def shift_coord(x, delta):\n    return x - delta\n",
            "pipeline.py": "from geometry import shift_coord\n\ndef translate(pt, offset):\n    return [shift_coord(p, offset) for p in pt]\n",
        },
        "test_file": "tests/test_geo.py",
        "test_code": "from pipeline import translate\n\nres = translate([1, 2, 3], 10)\nassert res == [11, 12, 13], f'Got {res}'\nprint('GEO TEST PASSED')\n",
    },
]


def run_swe_benchmark():
    print("=" * 76)
    print("IMF Multi-File SWE Autonomous Benchmark")
    print("=" * 76)

    agent = MultiFileSWEAgent()
    passed_count = 0
    total = len(BENCHMARK_SCENARIOS)
    start_all = time.perf_counter()

    for idx, sc in enumerate(BENCHMARK_SCENARIOS, 1):
        name = sc["name"]
        print(f"\n[{idx}/{total}] Running: {name}")
        print(f"    Description: {sc['description']}")

        t0 = time.perf_counter()
        result = agent.run_self_improving_loop(
            project_files=sc["project_files"],
            test_file=sc["test_file"],
            test_code=sc["test_code"],
        )
        dt = time.perf_counter() - t0

        if result["success"] and result["repaired"]:
            passed_count += 1
            print(f"    [✓] RESOLVED in {dt*1000:.1f}ms")
            for fpath, patched in result["patched_files"].items():
                print(f"        -> Patched {fpath}: {repr(patched.strip())}")
        else:
            print(f"    [✗] FAILED: {result}")

    elapsed = time.perf_counter() - start_all
    print("\n" + "=" * 76)
    print(f"Benchmark Complete: {passed_count}/{total} Passed ({passed_count/total*100:.1f}%) in {elapsed:.2f}s")
    print("=" * 76)
    return passed_count == total


if __name__ == "__main__":
    success = run_swe_benchmark()
    sys.exit(0 if success else 1)
