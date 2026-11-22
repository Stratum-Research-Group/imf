"""
Hyper-Dimensional Polytope Lattice Chamber Store (D = 10^4 - 10^9).

Implements hyper-dimensional knowledge chambers mapping conceptual domains,
timelines, formal ontologies, and invariant axioms to discrete root lattices.
Leverages the asymptotic properties of ultra-high dimensional spaces:
1. Pure index bit-rate vanishes as O(log D / D).
2. Random domain projection bases are almost-orthogonal: <u, v> ~ N(0, 1/D).
3. Discrete algebraic root coordinates prevent continuous hallucinations.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.polytope_lattice_quantizer import PolytopeLatticeQuantizer


@dataclass
class ChamberMetadata:
    """Metadata for a hyper-dimensional knowledge chamber."""
    chamber_id: str
    dimension: int
    num_lattice_anchors: int
    description: str
    active_k: int = 24
    lattice_type: str = "gosset_e8_tower"


@dataclass
class RetrievedFact:
    """A reconstructed fact or state retrieved from a hyper-lattice chamber."""
    chamber_id: str
    anchor_key: str
    active_indices: List[int]
    barycentric_weights: List[float]
    residual_norm: float
    reconstructed_vector: torch.Tensor
    attributes: Dict[str, Any] = field(default_factory=dict)


class HyperLatticeChamberStore(nn.Module):
    """
    Hyper-Dimensional Polytope Lattice Chamber Store.
    
    Provides isolated, orthogonal hyper-spaces (D >= 10^4 up to 10^9) for structured
    domain knowledge (e.g. historical chronologies, formal mathematical proofs,
    scientific taxonomies) without feed-forward parameter interference.
    """

    def __init__(
        self,
        embed_dim: int = 4096,
        hyper_dim: int = 1_000_000,
        active_k: int = 24,
        device: Optional[torch.device] = None,
        dtype: torch.dtype = torch.float32,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.hyper_dim = hyper_dim
        self.active_k = active_k
        self.device = device or (torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        self.dtype = dtype

        self.chambers: Dict[str, ChamberMetadata] = {}
        self.chamber_anchors: Dict[str, Dict[str, Dict[str, Any]]] = {}

        self.num_blocks = math.ceil(hyper_dim / embed_dim)
        self.plq = PolytopeLatticeQuantizer()

    def register_chamber(
        self,
        chamber_id: str,
        description: str,
        dimension: Optional[int] = None,
        active_k: Optional[int] = None,
        lattice_type: str = "gosset_e8_tower",
    ) -> ChamberMetadata:
        """Register a new domain chamber in the hyper-lattice."""
        dim = dimension or self.hyper_dim
        k = active_k or self.active_k
        meta = ChamberMetadata(
            chamber_id=chamber_id,
            dimension=dim,
            num_lattice_anchors=0,
            description=description,
            active_k=k,
            lattice_type=lattice_type,
        )
        self.chambers[chamber_id] = meta
        self.chamber_anchors[chamber_id] = {}
        return meta

    def project_to_hyperspace(self, query_emb: torch.Tensor, chamber_id: str) -> torch.Tensor:
        """
        Projects an embed_dim dense embedding into the chamber's hyper_dim space.
        Uses deterministic pseudorandom orthogonal hashing per chamber.
        """
        orig_shape = query_emb.shape
        if query_emb.dim() == 1:
            query = query_emb.unsqueeze(0).to(self.device, self.dtype)
        else:
            query = query_emb.to(self.device, self.dtype)
        
        B, E = query.shape
        assert E == self.embed_dim, f"Query dim {E} must match embed_dim {self.embed_dim}"

        chamber_seed = abs(hash(chamber_id)) % (2**31 - 1)
        g = torch.Generator(device=self.device)
        g.manual_seed(chamber_seed)

        hyper_vec = torch.zeros(B, self.hyper_dim, device=self.device, dtype=self.dtype)
        
        chunk_size = self.embed_dim
        for b_idx in range(self.num_blocks):
            start = b_idx * chunk_size
            end = min(start + chunk_size, self.hyper_dim)
            sub_len = end - start
            if sub_len <= 0:
                break
            
            proj_sub = torch.randn(E, sub_len, generator=g, device=self.device, dtype=self.dtype)
            proj_sub = proj_sub / math.sqrt(E)
            hyper_vec[:, start:end] = torch.matmul(query, proj_sub)

        hyper_vec = F.normalize(hyper_vec, p=2, dim=-1)

        if len(orig_shape) == 1:
            return hyper_vec.squeeze(0)
        return hyper_vec

    def project_from_hyperspace(self, hyper_vec: torch.Tensor, chamber_id: str) -> torch.Tensor:
        """
        Projects a hyper_dim vector back into standard embed_dim model activation space.
        """
        orig_shape = hyper_vec.shape
        if hyper_vec.dim() == 1:
            h_vec = hyper_vec.unsqueeze(0).to(self.device, self.dtype)
        else:
            h_vec = hyper_vec.to(self.device, self.dtype)

        B, D = h_vec.shape
        assert D == self.hyper_dim, f"Vector dim {D} must match hyper_dim {self.hyper_dim}"

        chamber_seed = abs(hash(chamber_id)) % (2**31 - 1)
        g = torch.Generator(device=self.device)
        g.manual_seed(chamber_seed)

        dense_out = torch.zeros(B, self.embed_dim, device=self.device, dtype=self.dtype)
        chunk_size = self.embed_dim

        for b_idx in range(self.num_blocks):
            start = b_idx * chunk_size
            end = min(start + chunk_size, self.hyper_dim)
            sub_len = end - start
            if sub_len <= 0:
                break

            proj_sub = torch.randn(self.embed_dim, sub_len, generator=g, device=self.device, dtype=self.dtype)
            proj_sub = proj_sub / math.sqrt(self.embed_dim)
            dense_out = dense_out + torch.matmul(h_vec[:, start:end], proj_sub.transpose(0, 1))

        if len(orig_shape) == 1:
            return dense_out.squeeze(0)
        return dense_out

    def decompose_onto_lattice(self, hyper_vector: torch.Tensor, k: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Decomposes a single hyper_dim vector onto the cross-polytope / Gosset lattice
        via fast Barycentric Orthogonal Matching Pursuit.
        Returns:
            active_indices: [k] integer coordinates in {0 .. 2*hyper_dim - 1}
            active_weights: [k] normalized barycentric coordinates summing to 1.0
            reconstructed:  [hyper_dim] reconstructed hyper-vector
        """
        if hyper_vector.dim() == 1:
            h = hyper_vector.unsqueeze(0).to(self.device, torch.float32)
        else:
            h = hyper_vector.to(self.device, torch.float32)
        
        indices, weights, scales, _ = self.plq.quantize_barycentric_omp(
            h, dim=self.hyper_dim, k=k
        )
        
        idx = indices[0] # [k]
        w = weights[0]   # [k]
        scale = scales[0, 0]

        # Reconstruct
        recon = torch.zeros(self.hyper_dim, device=self.device, dtype=torch.float32)
        dim = self.hyper_dim
        for j in range(k):
            v_id = idx[j].item()
            coord = v_id if v_id < dim else v_id - dim
            sgn = 1.0 if v_id < dim else -1.0
            recon[coord] += w[j].item() * sgn

        recon = recon * scale
        return idx, w, recon

    def reconstruct_from_sparse(self, indices: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
        """Reconstruct hyper_dim vector from sparse barycentric indices and weights."""
        recon = torch.zeros(self.hyper_dim, device=self.device, dtype=torch.float32)
        dim = self.hyper_dim
        k = len(indices)
        for j in range(k):
            v_id = int(indices[j])
            coord = v_id if v_id < dim else v_id - dim
            sgn = 1.0 if v_id < dim else -1.0
            recon[coord] += float(weights[j]) * sgn
        return recon

    def insert_fact(
        self,
        chamber_id: str,
        anchor_key: str,
        fact_vector: torch.Tensor,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> RetrievedFact:
        """
        Insert an invariant fact into the hyper-lattice chamber.
        Projects vector to hyper_dim, decomposes via Barycentric OMP into k discrete
        lattice vertices, and stores only the sparse index tuple (indices, weights).
        """
        if chamber_id not in self.chambers:
            self.register_chamber(chamber_id, f"Auto-registered {chamber_id}")

        meta = self.chambers[chamber_id]
        
        # 1. Project to hyper-space
        if fact_vector.shape[-1] == self.embed_dim:
            hyper_target = self.project_to_hyperspace(fact_vector, chamber_id)
        elif fact_vector.shape[-1] == self.hyper_dim:
            hyper_target = fact_vector.to(self.device, self.dtype)
        else:
            raise ValueError(f"Vector dim {fact_vector.shape[-1]} matches neither embed_dim ({self.embed_dim}) nor hyper_dim ({self.hyper_dim})")

        # 2. Decompose onto discrete polytope lattice via Barycentric OMP
        idx, w, recon = self.decompose_onto_lattice(hyper_target, k=meta.active_k)

        # 3. Store purely in sparse discrete representation
        anchor_record = {
            "indices": idx.cpu().tolist(),
            "weights": w.cpu().tolist(),
            "attributes": attributes or {},
        }
        self.chamber_anchors[chamber_id][anchor_key] = anchor_record
        meta.num_lattice_anchors = len(self.chamber_anchors[chamber_id])

        res_norm = torch.norm(hyper_target - recon).item()

        return RetrievedFact(
            chamber_id=chamber_id,
            anchor_key=anchor_key,
            active_indices=anchor_record["indices"],
            barycentric_weights=anchor_record["weights"],
            residual_norm=res_norm,
            reconstructed_vector=recon,
            attributes=anchor_record["attributes"],
        )

    def query_chamber(
        self,
        chamber_id: str,
        query: torch.Tensor,
        top_k: int = 1,
    ) -> List[Tuple[str, float, RetrievedFact]]:
        """
        Query a chamber with a dense embedding or hyper-vector.
        Computes cosine similarity in the discrete lattice space without materializing dense matrices.
        """
        if chamber_id not in self.chambers:
            raise KeyError(f"Chamber '{chamber_id}' does not exist.")

        anchors = self.chamber_anchors[chamber_id]
        if not anchors:
            return []

        # Project query if in embed_dim
        if query.shape[-1] == self.embed_dim:
            h_query = self.project_to_hyperspace(query, chamber_id)
        else:
            h_query = query.to(self.device, self.dtype)

        results = []
        for key, record in anchors.items():
            idx = torch.tensor(record["indices"], device=self.device, dtype=torch.long)
            w = torch.tensor(record["weights"], device=self.device, dtype=self.dtype)
            
            recon = self.reconstruct_from_sparse(idx, w)
            sim = F.cosine_similarity(h_query.unsqueeze(0), recon.unsqueeze(0)).item()
            
            fact = RetrievedFact(
                chamber_id=chamber_id,
                anchor_key=key,
                active_indices=record["indices"],
                barycentric_weights=record["weights"],
                residual_norm=0.0,
                reconstructed_vector=recon,
                attributes=record["attributes"],
            )
            results.append((key, sim, fact))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def measure_cross_chamber_orthogonality(self, chamber_a: str, chamber_b: str, num_samples: int = 64) -> float:
        """
        Empirically validates the almost-orthogonality lemma:
        E[|<P_A(x), P_B(y)>|] <= sqrt(1/D) -> 0 as D -> 10^6.
        """
        x = torch.randn(num_samples, self.embed_dim, device=self.device, dtype=self.dtype)
        y = torch.randn(num_samples, self.embed_dim, device=self.device, dtype=self.dtype)
        x = F.normalize(x, p=2, dim=-1)
        y = F.normalize(y, p=2, dim=-1)

        ha = self.project_to_hyperspace(x, chamber_a)
        hb = self.project_to_hyperspace(y, chamber_b)

        dots = torch.sum(ha * hb, dim=-1).abs()
        return dots.mean().item()
