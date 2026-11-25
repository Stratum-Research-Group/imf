"""
tests/test_corpus_sealing_daemon.py
Tests the autonomous block sealing daemon and manifest integrity updater.
"""

import os
import json
import tempfile
from pathlib import Path
from imf.daemons.corpus_sealing_daemon import compute_sha256, seal_completed_block


def test_corpus_sealing_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        stream_file = tmp_path / "temp_block.jsonl"
        with open(stream_file, "w") as f:
            for i in range(10):
                f.write(f'{{"step": {i}}}\n')

        h = compute_sha256(stream_file)
        assert len(h) == 64
        # Verification that less than 1M steps does not falsely seal
        sealed = seal_completed_block(999, stream_file)
        assert sealed is None
