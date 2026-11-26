# Paper 829: Eventfd-Gated DMA Rings and Non-Blocking Wakeup Latency Audits

We present an experimental audit of eventfd-gated io_uring submission/completion rings under high-frequency IPC streaming in Linux 6.18, documenting sub-microsecond event delivery under 100% thread saturation.
