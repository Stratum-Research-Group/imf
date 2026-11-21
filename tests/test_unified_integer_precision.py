import torch
import pytest
from imf.unified_integer_precision import UnifiedIntegerQuantizer, ETHQuantizedLinear

def test_unified_int4_quantization_roundtrip():
    torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Random tensor of shape [128, 256]
    orig = torch.randn(128, 256, device=device)
    
    # Quantize to packed INT4
    packed, scales = UnifiedIntegerQuantizer.quantize_to_int4(orig, block_size=64)
    
    # 4 bits per value means packed size is exactly half of total elements
    assert packed.numel() == orig.numel() // 2
    
    # Dequantize back using Triton JIT kernel
    recon = UnifiedIntegerQuantizer.dequantize_from_int4(packed, scales, orig.shape, block_size=64)
    
    # Bounded reconstruction error: for INT4, cosine similarity must be > 0.98
    cos_sim = torch.cosine_similarity(orig.flatten(), recon.flatten(), dim=0).item()
    assert cos_sim > 0.98, f"INT4 cosine similarity too low: {cos_sim}"

def test_unified_int8_quantization_roundtrip():
    torch.manual_seed(42)
    orig = torch.randn(64, 128)
    q, scales = UnifiedIntegerQuantizer.quantize_to_int8(orig, block_size=128)
    recon = UnifiedIntegerQuantizer.dequantize_from_int8(q, scales, block_size=128)
    
    cos_sim = torch.cosine_similarity(orig.flatten(), recon.flatten(), dim=0).item()
    assert cos_sim > 0.995, f"INT8 cosine similarity too low: {cos_sim}"

def test_eth_quantized_linear_forward():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    layer = ETHQuantizedLinear(128, 256, precision="int4").to(device)
    x = torch.randn(4, 128, device=device)
    out = layer(x)
    assert out.shape == (4, 256)
    assert not torch.isnan(out).any()
