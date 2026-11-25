.PHONY: test test-forensics test-kernels all

test:
	~/.local/share/mise/installs/uv/latest/.mise-bins/uv run python scripts/run_and_record_tests.py

test-forensics:
	~/.local/share/mise/installs/uv/latest/.mise-bins/uv run pytest tests/test_benchmark_forensic_regressions.py

test-kernels:
	~/.local/share/mise/installs/uv/latest/.mise-bins/uv run pytest tests/test_omni_block.py
