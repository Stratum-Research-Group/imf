"""
imf/pipelined_multimodal_streamer.py
Asynchronous Double-Buffered Multimodal Streaming Queue with dual CUDA Streams.
Overlaps Host-to-Device (H2D) tensor ingestion/preprocessing with GPU SSM/OmniBlock
Lie group state propagation.
"""

import time
import torch
import torch.nn as nn
from typing import Optional, Tuple, Iterator
from imf.omni_block import IMFOmniBlock


class PipelinedMultimodalStreamer:
    """
    Double-buffered asynchronous streaming pipeline for IMF continuous multimodal inputs.
    Utilizes two concurrent CUDA streams:
    - transfer_stream: handles non-blocking Host-to-Device memory copies and layout transforms.
    - compute_stream: executes IMFOmniBlock unitary SSM recurrence and attention.
    """
    def __init__(self, block: IMFOmniBlock, d_model: int = 128, tokens_per_frame: int = 64, device: str = "cuda"):
        self.block = block.to(device).eval()
        self.device = torch.device(device)
        self.d_model = d_model
        self.tokens_per_frame = tokens_per_frame
        
        self.is_cuda = self.device.type == "cuda"
        if self.is_cuda:
            self.transfer_stream = torch.cuda.Stream(device=self.device)
            self.compute_stream = torch.cuda.Stream(device=self.device)
        else:
            self.transfer_stream = None
            self.compute_stream = None
            
        # Pinned host double buffers if CUDA available
        if self.is_cuda:
            self.buf_host_0 = torch.empty((1, tokens_per_frame, d_model), dtype=torch.float32, pin_memory=True)
            self.buf_host_1 = torch.empty((1, tokens_per_frame, d_model), dtype=torch.float32, pin_memory=True)
            self.buf_dev_0 = torch.empty((1, tokens_per_frame, d_model), dtype=torch.float32, device=self.device)
            self.buf_dev_1 = torch.empty((1, tokens_per_frame, d_model), dtype=torch.float32, device=self.device)
        
        self.state = None

    def stream_frames(self, frame_generator: Iterator[torch.Tensor], num_frames: int) -> Tuple[float, float, list]:
        """
        Executes pipelined double-buffered streaming over num_frames.
        Returns:
            fps: Frames per second processed
            tokens_per_sec: Tokens per second sustained
            latencies_ms: Per-frame compute latency list
        """
        latencies_ms = []
        if not self.is_cuda:
            # Fallback to synchronous execution
            t_start = time.perf_counter()
            with torch.no_grad():
                for frame in frame_generator:
                    t0 = time.perf_counter()
                    out, self.state = self.block.forward_ssm(self.block.norm1(frame.to(self.device)), initial_state=self.state, return_final_state=True)
                    latencies_ms.append((time.perf_counter() - t0) * 1000.0)
            t_total = time.perf_counter() - t_start
            fps = len(latencies_ms) / max(t_total, 1e-6)
            return fps, fps * self.tokens_per_frame, latencies_ms

        # Double-buffered CUDA pipeline
        host_bufs = [self.buf_host_0, self.buf_host_1]
        dev_bufs = [self.buf_dev_0, self.buf_dev_1]
        
        torch.cuda.synchronize()
        t_start = time.perf_counter()
        
        curr_buf = 0
        frames_iter = iter(frame_generator)
        
        # Prime first frame into buf 0
        first_frame = next(frames_iter)
        host_bufs[curr_buf].copy_(first_frame)
        with torch.cuda.stream(self.transfer_stream):
            dev_bufs[curr_buf].copy_(host_bufs[curr_buf], non_blocking=True)
            
        with torch.no_grad():
            for f in range(num_frames):
                # Wait for transfer of current buffer to finish before compute
                self.compute_stream.wait_stream(self.transfer_stream)
                
                # Transfer next frame in background (if any remains)
                next_buf = 1 - curr_buf
                if f + 1 < num_frames:
                    try:
                        next_frame = next(frames_iter)
                        host_bufs[next_buf].copy_(next_frame)
                        with torch.cuda.stream(self.transfer_stream):
                            dev_bufs[next_buf].copy_(host_bufs[next_buf], non_blocking=True)
                    except StopIteration:
                        pass
                
                # Execute computation on compute stream
                with torch.cuda.stream(self.compute_stream):
                    t0 = time.perf_counter()
                    dev_in = dev_bufs[curr_buf]
                    out, self.state = self.block.forward_ssm(
                        self.block.norm1(dev_in),
                        initial_state=self.state,
                        return_final_state=True
                    )
                    
                self.compute_stream.synchronize()
                latencies_ms.append((time.perf_counter() - t0) * 1000.0)
                curr_buf = next_buf

        torch.cuda.synchronize()
        t_total = time.perf_counter() - t_start
        fps = num_frames / max(t_total, 1e-6)
        tokens_per_sec = fps * self.tokens_per_frame
        
        return fps, tokens_per_sec, latencies_ms
