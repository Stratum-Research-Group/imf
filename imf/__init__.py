"""
IMF: Interaction Primitive Families & Higher-Dimensional Polytope Virtual Grid Memory.
Core exports:
- FusedSAVGLayer: Triton-accelerated Symmetric-Antisymmetric Virtual Grid Attention
- ConfigurablePolytopeConnector: Higher-Dimensional Polytope Landmark Connectors
- HigherAritySimplexBinding: Arity-3 and Arity-4 CP-factorized simplex tensor bindings
- SAVGScanFunction: Autograd functional interface for SAVG scan
"""

from triton_savg_kernel import FusedSAVGLayer, SAVGScanFunction, pytorch_reference_savg_scan
from multihead_savg import MultiHeadSAVGLayer
from polytope_connector import ConfigurablePolytopeConnector
from higher_arity_simplex import HigherAritySimplexBinding

__version__ = "0.1.0"
__all__ = [
    "FusedSAVGLayer",
    "MultiHeadSAVGLayer",
    "SAVGScanFunction",
    "pytorch_reference_savg_scan",
    "ConfigurablePolytopeConnector",
    "HigherAritySimplexBinding",
]
