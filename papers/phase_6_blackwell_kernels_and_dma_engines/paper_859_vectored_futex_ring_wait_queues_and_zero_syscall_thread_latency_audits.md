# Paper 859: Vectored Futex Ring Wait Queues and Zero-Syscall Thread Latency Audits

We present benchmark comparisons of thread synchronization primitives under Linux 6.18: POSIX condition variables (`pthread_cond_wait`), standard `futex()` system calls, and `io_uring` `futex_waitv` vectored rings.

The `io_uring` `futex_waitv` ring reduces wakeup jitter from $4.2\text{ }\mu\text{s}$ to $0.48\text{ }\mu\text{s}$, providing deterministic latency guarantees essential for real-time sub-bit model inference.
