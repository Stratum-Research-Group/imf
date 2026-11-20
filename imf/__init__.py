"""
IMF: Interaction Primitive Families & Higher-Dimensional Polytope Virtual Grid Memory.
Core exports:
- FusedSAVGLayer: Triton-accelerated Symmetric-Antisymmetric Virtual Grid Attention
- ConfigurablePolytopeConnector: Higher-Dimensional Polytope Landmark Connectors
- HigherAritySimplexBinding: Arity-3 and Arity-4 CP-factorized simplex tensor bindings
- SAVGScanFunction: Autograd functional interface for SAVG scan
"""

__version__ = "0.5.0"
__all__ = [
    "FusedSAVGLayer",
    "MultiHeadSAVGLayer",
    "SAVGScanFunction",
    "pytorch_reference_savg_scan",
    "ConfigurablePolytopeConnector",
    "HigherAritySimplexBinding",
    "ContinuousSimplexConvolutionalBinding",
    "SU2GaugeSimplicialComplex",
    "AdaptivePolytopeSubdivision",
    "ContinuousLieGroupSSM",
    "IMFOmniBlock",
    "HyperbolicPolytopeTiling",
    "BPETokenizer",
    "CodeBPETokenizer",
    "PolytopeMixtureOfExperts",
    "PolytopeExpert",
    "IMFJointReconPredictorLM",
    "BidirectionalCutReasoning",
]

from triton_savg_kernel import FusedSAVGLayer, SAVGScanFunction, pytorch_reference_savg_scan
from multihead_savg import MultiHeadSAVGLayer
from polytope_connector import ConfigurablePolytopeConnector
from higher_arity_simplex import HigherAritySimplexBinding, ContinuousSimplexConvolutionalBinding
from imf.gauge_polytope_complex import SU2GaugeSimplicialComplex
from imf.adaptive_mesh_refinement import AdaptivePolytopeSubdivision
from imf.continuous_lie_ssm import ContinuousLieGroupSSM
from imf.omni_block import IMFOmniBlock
from imf.hyperbolic_polytope_tiling import HyperbolicPolytopeTiling
from imf.bpe_tokenizer import BPETokenizer
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.polytope_moe import PolytopeMixtureOfExperts, PolytopeExpert
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.eth_cut_reasoning import BidirectionalCutReasoning
