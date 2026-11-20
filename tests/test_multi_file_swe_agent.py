import pytest
from imf.multi_file_swe_agent import MultiFileSWEAgent


def test_multi_file_autonomous_swe_agent_loop():
    agent = MultiFileSWEAgent()

    # Define a multi-file project with a planted arithmetic bug in core/engine.py
    project_files = {
        "core/__init__.py": "",
        "core/engine.py": (
            "def compute_total(items: list[int]) -> int:\n"
            "    total = 0\n"
            "    for x in items:\n"
            "        total = total - x\n"  # Bug: subtraction instead of addition
            "    return total\n"
        ),
        "app.py": (
            "from core.engine import compute_total\n"
            "def run_app():\n"
            "    return compute_total([10, 20, 30])\n"
        ),
    }

    test_file = "tests/test_app.py"
    test_code = (
        "import sys\n"
        "from app import run_app\n"
        "res = run_app()\n"
        "assert res == 60, f'Expected 60, got {res}'\n"
        "print('Assertion verified!')\n"
    )

    result = agent.run_self_improving_loop(project_files, test_file, test_code)

    assert result["success"] is True
    assert result["repaired"] is True
    assert "core/engine.py" in result["patched_files"]
    assert "total = total + x" in result["patched_files"]["core/engine.py"]
