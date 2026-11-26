# Paper 849: Direct DMA-BUF Memory Pipelines and Zero-Copy Latency Audits

We present extensive latency benchmarks of the Linux 6.18 `io_uring` direct DMA-BUF ring engine under heavy concurrent memory traffic.

Comparing traditional `read()`/`write()` system calls, memory-mapped I/O (`mmap`), and `io_uring` direct DMA-BUF registration, the direct DMA-BUF pipeline reduces P99 latency from $18.4\text{ }\mu\text{s}$ to $1.1\text{ }\mu\text{s}$, a 16.7x improvement in tail latency critical for sub-bit streaming.
