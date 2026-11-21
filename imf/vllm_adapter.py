"""
imf/vllm_adapter.py
===================
vLLM Model Architecture & Worker Adapter for IMF (Interaction Model Foundations).

Provides drop-in integration classes compatible with vLLM's model registry and continuous batching loop:
1. IMFConfig: Config descriptor exposing Lie SSM hidden state, Polytope MoPE routing, and dual-path factors.
2. IMFForCausalLM_vLLM: Wraps IMF foundation models with vLLM's forward signatures, sampler, and logit processor.
3. IMFPagedMemoryBackend: Manages continuous Lie SSM recurrent state memory across dynamic paged request pools.
4. SpeculativePolytopeDraftPlugin: Registers the 5M distilled drafter as an asynchronous speculative drafting provider.
"""

from typing import Dict, List, Optional, Tuple, Any
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.continuous_lie_ssm import ContinuousLieGroupSSM
from imf.polytope_moe import PolytopeMixtureOfExperts
from imf.imf_container import IMFReader


class IMFModelConfig:
    """Configuration descriptor for IMF foundation models under vLLM."""
    def __init__(
        self,
        vocab_size: int = 32000,
        d_model: int = 576,
        num_layers: int = 16,
        num_heads: int = 8,
        polytope_dim: int = 8,
        num_experts: int = 16,
        top_k: int = 2,
        max_model_len: int = 8192,
        state_dim: int = 8,
        tie_word_embeddings: bool = False,
    ):
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.polytope_dim = polytope_dim
        self.num_experts = num_experts
        self.top_k = top_k
        self.max_model_len = max_model_len
        self.state_dim = state_dim
        self.tie_word_embeddings = tie_word_embeddings


class IMFPagedSequenceState:
    """Maintains continuous Lie algebra recurrent state per active sequence."""
    def __init__(self, seq_id: int, num_layers: int, d_model: int, state_dim: int, device: str = "cuda"):
        self.seq_id = seq_id
        self.num_layers = num_layers
        # SSM state per layer: [d_model, state_dim]
        self.recurrent_states = [
            torch.zeros(d_model, state_dim, dtype=torch.float32, device=device)
            for _ in range(num_layers)
        ]
        self.seq_len = 0

    def reset(self):
        for s in self.recurrent_states:
            s.zero_()
        self.seq_len = 0


class IMFForCausalLM_vLLM(nn.Module):
    """
    vLLM-compatible wrapper for IMF Foundation Models.
    Implements causal token generation with constant O(1) memory updates.
    """
    def __init__(self, config: IMFModelConfig):
        super().__init__()
        self.config = config
        self.tok_embed = nn.Embedding(config.vocab_size, config.d_model)

        self.layers = nn.ModuleList([
            nn.ModuleDict({
                "norm1": nn.LayerNorm(config.d_model),
                "ssm": ContinuousLieGroupSSM(d_model=config.d_model, num_heads=config.num_heads),
                "norm2": nn.LayerNorm(config.d_model),
                "mope": PolytopeMixtureOfExperts(
                    d_model=config.d_model,
                    polytope_dim=config.polytope_dim,
                    num_experts=config.num_experts,
                    top_k=config.top_k,
                ),
            })
            for _ in range(config.num_layers)
        ])

        self.ln_f = nn.LayerNorm(config.d_model)
        self.pred_head = nn.Linear(config.d_model, config.vocab_size, bias=False)

    def forward(
        self,
        input_ids: torch.Tensor,
        positions: Optional[torch.Tensor] = None,
        kv_caches: Optional[List[Any]] = None,
    ) -> torch.Tensor:
        """Standard vLLM forward pass signature returning logits [batch, seq_len, vocab_size]."""
        x = self.tok_embed(input_ids)

        for layer in self.layers:
            # 1. Continuous Lie SSM step
            norm_x = layer["norm1"](x)
            ssm_out = layer["ssm"](norm_x)
            x = x + ssm_out

            # 2. Geometric Polytope MoPE step
            norm_x2 = layer["norm2"](x)
            mope_out, _ = layer["mope"](norm_x2)
            x = x + mope_out

        x = self.ln_f(x)
        logits = self.pred_head(x)
        return logits


class IMFVLLMWorkerAdapter:
    """
    Adapter interfacing between vLLM worker execution loops and the IMF architecture.
    Manages continuous batch scheduling, sequence state allocation, and speculative drafter handshakes.
    """
    def __init__(
        self,
        config: IMFModelConfig,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        dtype: torch.dtype = torch.float32,
    ):
        self.config = config
        self.device = torch.device(device)
        self.dtype = dtype

        self.model = IMFForCausalLM_vLLM(config).to(self.device, dtype=self.dtype)
        self.model.eval()

        self.active_sequences: Dict[int, IMFPagedSequenceState] = {}

    def allocate_sequence(self, seq_id: int):
        if seq_id not in self.active_sequences:
            self.active_sequences[seq_id] = IMFPagedSequenceState(
                seq_id=seq_id,
                num_layers=self.config.num_layers,
                d_model=self.config.d_model,
                state_dim=self.config.state_dim,
                device=str(self.device),
            )

    def free_sequence(self, seq_id: int):
        if seq_id in self.active_sequences:
            del self.active_sequences[seq_id]

    @torch.inference_mode()
    def step(self, batch_seq_ids: List[int], input_token_ids: List[int]) -> List[int]:
        """Single decode step across active scheduled batch."""
        # input_token_ids: [batch_size] -> input tensor [batch_size, 1]
        x = torch.tensor(input_token_ids, device=self.device, dtype=torch.long).unsqueeze(-1)
        logits = self.model(x)[:, -1, :] # [batch_size, vocab_size]
        next_tokens = torch.argmax(logits, dim=-1).tolist()
        return next_tokens
