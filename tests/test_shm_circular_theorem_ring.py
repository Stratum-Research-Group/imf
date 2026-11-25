"""
tests/test_shm_circular_theorem_ring.py
Tests the zero-copy shared memory circular ring buffer push/pop operations.
"""

import os
import tempfile
import numpy as np
from imf.shm_circular_theorem_ring import SharedMemoryTheoremRing


def test_shm_circular_theorem_ring():
    with tempfile.TemporaryDirectory() as tmpdir:
        shm_path = os.path.join(tmpdir, "test_ring.shm")
        ring_writer = SharedMemoryTheoremRing(shm_path=shm_path, capacity=8, step_len=16, create=True)
        ring_reader = SharedMemoryTheoremRing(shm_path=shm_path, capacity=8, step_len=16, create=False)

        # Buffer should be initially empty
        assert ring_reader.pop() is None

        # Push items
        v1 = np.ones(16, dtype=np.float32) * 3.14
        v2 = np.ones(16, dtype=np.float32) * 2.71
        assert ring_writer.push(v1) is True
        assert ring_writer.push(v2) is True

        # Pop items
        r1 = ring_reader.pop()
        assert r1 is not None
        np.testing.assert_allclose(r1, v1)

        r2 = ring_reader.pop()
        assert r2 is not None
        np.testing.assert_allclose(r2, v2)

        assert ring_reader.pop() is None

        ring_writer.close()
        ring_reader.close()
