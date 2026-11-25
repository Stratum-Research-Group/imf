"""
imf/shm_circular_theorem_ring.py
Zero-Copy POSIX Shared-Memory Circular Theorem Ring Buffer.
Enables lock-free, zero-copy streaming of tokenized theorem steps directly
from the MegaGym candidate generator into the continuous student distillation trainer
without touching physical disks.
"""

import os
import sys
import mmap
import time
import struct
import numpy as np
from typing import Optional, Tuple

MAGIC = b"THMR" # Theorem Ring
HEADER_STRUCT = struct.Struct("<4sIIII") # magic, head, tail, capacity, step_len


class SharedMemoryTheoremRing:
    def __init__(self, shm_path: str = "/dev/shm/imf_theorems_ring", capacity: int = 1024, step_len: int = 128, create: bool = True):
        self.shm_path = shm_path
        self.capacity = capacity
        self.step_len = step_len
        self.payload_bytes = capacity * step_len * 4 # float32
        self.total_bytes = HEADER_STRUCT.size + self.payload_bytes

        if create:
            with open(shm_path, "wb") as f:
                f.write(b"\x00" * self.total_bytes)
            self._fd = os.open(shm_path, os.O_RDWR)
            self.mm = mmap.mmap(self._fd, self.total_bytes)
            # Write header
            HEADER_STRUCT.pack_into(self.mm, 0, MAGIC, 0, 0, capacity, step_len)
        else:
            if not os.path.exists(shm_path):
                raise FileNotFoundError(f"SHM ring buffer {shm_path} does not exist.")
            self._fd = os.open(shm_path, os.O_RDWR)
            self.mm = mmap.mmap(self._fd, self.total_bytes)
            magic, _, _, self.capacity, self.step_len = HEADER_STRUCT.unpack_from(self.mm, 0)
            if magic != MAGIC:
                raise ValueError("Corrupt SHM ring buffer magic bytes.")

        self.payload_offset = HEADER_STRUCT.size

    def push(self, step_tensor: np.ndarray) -> bool:
        """
        Pushes a single step [step_len] float32 into the ring buffer.
        """
        magic, head, tail, capacity, step_len = HEADER_STRUCT.unpack_from(self.mm, 0)
        next_head = (head + 1) % capacity
        if next_head == tail:
            # Buffer full
            return False

        offset = self.payload_offset + head * (step_len * 4)
        data = np.ascontiguousarray(step_tensor, dtype=np.float32).tobytes()
        self.mm[offset : offset + len(data)] = data

        # Update head
        HEADER_STRUCT.pack_into(self.mm, 0, magic, next_head, tail, capacity, step_len)
        return True

    def pop(self) -> Optional[np.ndarray]:
        """
        Pops a single step [step_len] float32 from the ring buffer.
        """
        magic, head, tail, capacity, step_len = HEADER_STRUCT.unpack_from(self.mm, 0)
        if head == tail:
            # Buffer empty
            return None

        offset = self.payload_offset + tail * (step_len * 4)
        bytes_data = self.mm[offset : offset + step_len * 4]
        tensor = np.frombuffer(bytes_data, dtype=np.float32).copy()

        next_tail = (tail + 1) % capacity
        HEADER_STRUCT.pack_into(self.mm, 0, magic, head, next_tail, capacity, step_len)
        return tensor

    def close(self):
        try:
            self.mm.close()
            os.close(self._fd)
        except Exception:
            pass
