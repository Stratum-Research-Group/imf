// csrc/fused_blackwell_gqa_dequant.cu
// Production Fused Blackwell SM 12.0 Grouped-Query Attention (GQA) with In-Register KV Dequantization Kernel
// Ingests quantized INT8 KV cache with per-token floating-point scaling vectors,
// performing register-level on-the-fly dequantization and causal online LogSumExp attention.

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

extern "C" __global__ void fused_blackwell_gqa_dequant_kernel(
    const float* __restrict__ Q,         // [batch, num_q_heads, seq_len, head_dim]
    const int8_t* __restrict__ K_quant,  // [batch, num_kv_heads, seq_len, head_dim]
    const float* __restrict__ K_scale,   // [batch, num_kv_heads, seq_len]
    const int8_t* __restrict__ V_quant,  // [batch, num_kv_heads, seq_len, head_dim]
    const float* __restrict__ V_scale,   // [batch, num_kv_heads, seq_len]
    float* __restrict__ Out,             // [batch, num_q_heads, seq_len, head_dim]
    int batch_size,
    int num_q_heads,
    int num_kv_heads,
    int seq_len,
    int head_dim,
    float scale
) {
    int b = blockIdx.z / num_q_heads;
    int qh = blockIdx.z % num_q_heads;
    int q_idx = blockIdx.y; // query index 0 .. seq_len-1
    int d = blockIdx.x * blockDim.x + threadIdx.x; // head_dim index

    if (b >= batch_size || q_idx >= seq_len || d >= head_dim) return;

    int gqa_ratio = num_q_heads / num_kv_heads;
    int kvh = qh / gqa_ratio;

    size_t q_bh_offset = ((size_t)b * num_q_heads + qh) * ((size_t)seq_len * head_dim);
    size_t kv_bh_offset = ((size_t)b * num_kv_heads + kvh) * ((size_t)seq_len * head_dim);
    size_t kv_scale_offset = ((size_t)b * num_kv_heads + kvh) * (size_t)seq_len;

    const float* q_ptr = Q + q_bh_offset + (size_t)q_idx * head_dim;
    const int8_t* k_base = K_quant + kv_bh_offset;
    const float* k_sc_base = K_scale + kv_scale_offset;
    const int8_t* v_base = V_quant + kv_bh_offset;
    const float* v_sc_base = V_scale + kv_scale_offset;
    float* out_ptr = Out + q_bh_offset + (size_t)q_idx * head_dim;

    // Step 1: Online max score across causal sequence range j in [0, q_idx]
    float max_score = -1e30f;

    for (int j = 0; j <= q_idx; ++j) {
        const int8_t* k_ptr = k_base + (size_t)j * head_dim;
        float sc_k = k_sc_base[j];

        float dot = 0.0f;
        for (int k = 0; k < head_dim; ++k) {
            float dequant_k = (float)k_ptr[k] * sc_k;
            dot += q_ptr[k] * dequant_k;
        }
        float s = dot * scale;
        if (s > max_score) {
            max_score = s;
        }
    }

    // Step 2: Online sum of exponentials and weighted value state accumulation
    float sum_exp = 0.0f;
    float weighted_v = 0.0f;

    for (int j = 0; j <= q_idx; ++j) {
        const int8_t* k_ptr = k_base + (size_t)j * head_dim;
        float sc_k = k_sc_base[j];

        float dot = 0.0f;
        for (int k = 0; k < head_dim; ++k) {
            float dequant_k = (float)k_ptr[k] * sc_k;
            dot += q_ptr[k] * dequant_k;
        }
        float p = expf(dot * scale - max_score);
        sum_exp += p;

        float dequant_v = (float)v_base[(size_t)j * head_dim + d] * v_sc_base[j];
        weighted_v += p * dequant_v;
    }

    if (sum_exp > 0.0f) {
        out_ptr[d] = weighted_v / sum_exp;
    } else {
        out_ptr[d] = 0.0f;
    }
}

extern "C" int launch_fused_blackwell_gqa_dequant(
    const float* Q,
    const int8_t* K_quant,
    const float* K_scale,
    const int8_t* V_quant,
    const float* V_scale,
    float* Out,
    int batch_size,
    int num_q_heads,
    int num_kv_heads,
    int seq_len,
    int head_dim,
    float scale,
    cudaStream_t stream
) {
    if (!Q || !K_quant || !K_scale || !V_quant || !V_scale || !Out) return -1;
    if (batch_size <= 0 || num_q_heads <= 0 || num_kv_heads <= 0 || seq_len <= 0 || head_dim <= 0) return -1;
    if (num_q_heads % num_kv_heads != 0) return -1;

    int threads_x = (head_dim <= 64) ? 64 : ((head_dim <= 128) ? 128 : 256);
    dim3 block(threads_x);
    dim3 grid((head_dim + threads_x - 1) / threads_x, seq_len, batch_size * num_q_heads);

    fused_blackwell_gqa_dequant_kernel<<<grid, block, 0, stream>>>(
        Q, K_quant, K_scale, V_quant, V_scale, Out,
        batch_size, num_q_heads, num_kv_heads, seq_len, head_dim, scale
    );

    cudaError_t err = cudaGetLastError();
    return (err == cudaSuccess) ? 0 : (int)err;
}
