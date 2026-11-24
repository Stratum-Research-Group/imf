"""
IMF Polytope LRU Cache with Thread-Safe Telemetry Eviction
==========================================================
High-performance thread-safe LRU cache for high-dimensional polytope
centroid embeddings, geodesic metrics, and dequantized root weights.
Ensures zero-leak memory bounds during continuous multi-pass training.
"""

import time
import threading
from collections import OrderedDict
from typing import Any, Optional, Tuple


class PolytopeLRUCache:
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.lock = threading.Lock()
        
        # Telemetry counters
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.total_insert_time_ns = 0

    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            self.hits += 1
            # Move accessed entry to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key: str, value: Any) -> None:
        t0 = time.perf_counter_ns()
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                self.cache[key] = value
            else:
                if len(self.cache) >= self.capacity:
                    # Pop least recently used item (first item)
                    self.cache.popitem(last=False)
                    self.evictions += 1
                self.cache[key] = value
        elapsed = time.perf_counter_ns() - t0
        self.total_insert_time_ns += elapsed

    def telemetry(self) -> dict:
        with self.lock:
            total_lookups = self.hits + self.misses
            hit_rate = (self.hits / total_lookups * 100.0) if total_lookups > 0 else 0.0
            return {
                "capacity": self.capacity,
                "current_size": len(self.cache),
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "hit_rate_pct": round(hit_rate, 2),
                "total_lookups": total_lookups
            }

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0


def benchmark_polytope_lru():
    print("=" * 80)
    print("  IMF POLYTOPE LRU CACHE & EVICTION TELEMETRY BENCHMARK")
    print("=" * 80)
    
    cache = PolytopeLRUCache(capacity=500)
    
    # Pre-populate
    for i in range(500):
        cache.put(f"polytope_centroid_{i}", [0.1 * i, 0.2 * i])
        
    # Access patterns: 80% hits on hot subset 0..100, 20% misses/inserts
    t0 = time.perf_counter()
    lookups = 100000
    for i in range(lookups):
        if i % 5 != 0:
            # Hot hit
            key = f"polytope_centroid_{i % 100}"
            _ = cache.get(key)
        else:
            # New insert causing eviction
            key = f"new_polytope_tile_{i}"
            cache.put(key, [0.5, 0.5])
            
    elapsed = time.perf_counter() - t0
    stats = cache.telemetry()
    ops_sec = lookups / elapsed
    
    print(f"[*] Capacity: {stats['capacity']} | Final Size: {stats['current_size']}")
    print(f"[*] Hits: {stats['hits']} | Misses: {stats['misses']} | Evictions: {stats['evictions']}")
    print(f"[*] Hit Rate: {stats['hit_rate_pct']}%")
    print(f"[✓] Lookups Throughput: {ops_sec / 1e3:.2f} kops/sec ({elapsed * 1000:.2f} ms total)")
    print("=" * 80)


if __name__ == "__main__":
    benchmark_polytope_lru()
