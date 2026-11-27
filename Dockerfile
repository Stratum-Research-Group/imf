# Production Multi-Stage Dockerfile for The Sacred Sanctum
# Provides full reproducibility: Python 3.12, PyTorch, Triton, Lean 4 (Elan), and Sovereign API daemon.

FROM nvidia/cuda:12.6.0-runtime-ubuntu24.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Elan and Lean 4
ENV ELAN_HOME="/root/.elan"
ENV PATH="/root/.elan/bin:${PATH}"
RUN curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -y --default-toolchain leanprover/lean4:v4.16.0

WORKDIR /workspace

# Copy repository
COPY . /workspace

# Install python dependencies in venv
RUN python3 -m venv .venv && \
    .venv/bin/pip install --upgrade pip && \
    .venv/bin/pip install torch numpy scipy triton rich safetensors fastjsonschema

EXPOSE 8000

# Default entrypoint starts Sovereign API Daemon
CMD [".venv/bin/python", "scripts/serve_openai_compatible_api.py"]
