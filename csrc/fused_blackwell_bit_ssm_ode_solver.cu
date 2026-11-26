/*
 * fused_blackwell_bit_ssm_ode_solver.cu
 *
 * Microarchitectural CUDA SM 12.0 (Blackwell) Bitplane Continuous-Time State-Space (S4/SSM) ODE Solver.
 * Implements 4th-order Runge-Kutta (RK4) integration for continuous state-space systems:
 *    dx/dt = A x(t) + B u(t)
 * where u(t) is unpacked from 2-bit quantized bitplane streams, evaluated in warp registers.
 *
 * Compile:
 *   nvcc -O3 -shared -Xcompiler -fPIC -arch=sm_120 -o csrc/fused_blackwell_bit_ssm_ode_solver.so csrc/fused_blackwell_bit_ssm_ode_solver.cu
 */

#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>

#define WARP_SIZE 32
#define STATE_DIM 64

extern "C" __global__ void fused_blackwell_bit_ssm_ode_solver_kernel(
    const uint8_t* __restrict__ Bitplane_U,   // [batch, seq_len / 4, STATE_DIM]
    const float* __restrict__ A_diag,         // [STATE_DIM] (diagonal continuous system matrix)
    const float* __restrict__ B_vec,          // [STATE_DIM]
    const float* __restrict__ Scale_LUT,      // [4] dequantization LUT
    float* __restrict__ X_out,                // [batch, seq_len, STATE_DIM]
    int batch_size,
    int seq_len,
    float dt
) {
    int warp_id = (blockIdx.x * blockDim.x + threadIdx.x) / WARP_SIZE;
    int lane_id = threadIdx.x % WARP_SIZE;

    int total_warps = (gridDim.x * blockDim.x) / WARP_SIZE;
    int coords = batch_size * (STATE_DIM / 2); // Each lane handles 2 states (64 / 32 = 2)

    int d0 = lane_id * 2;
    int d1 = lane_id * 2 + 1;

    for (int b = warp_id; b < batch_size; b += total_warps) {
        float a0 = A_diag[d0];
        float a1 = A_diag[d1];
        float b_val0 = B_vec[d0];
        float b_val1 = B_vec[d1];

        float x0 = 0.0f;
        float x1 = 0.0f;

        for (int t = 0; t < seq_len; ++t) {
            // Unpack 2-bit symbol
            int byte_idx = (b * (seq_len / 4) + (t / 4)) * STATE_DIM;
            int bit_shift = (t % 4) * 2;
            
            uint8_t pack0 = Bitplane_U[byte_idx + d0];
            uint8_t pack1 = Bitplane_U[byte_idx + d1];

            float u0 = Scale_LUT[(pack0 >> bit_shift) & 0x03];
            float u1 = Scale_LUT[(pack1 >> bit_shift) & 0x03];

            // RK4 Integration for linear ODE dx/dt = A x + B u:
            // k1 = a * x + b * u
            // k2 = a * (x + 0.5 * dt * k1) + b * u
            // k3 = a * (x + 0.5 * dt * k2) + b * u
            // k4 = a * (x + dt * k3) + b * u
            // x_new = x + (dt / 6) * (k1 + 2*k2 + 2*k3 + k4)

            float k1_0 = a0 * x0 + b_val0 * u0;
            float k1_1 = a1 * x1 + b_val1 * u1;

            float k2_0 = a0 * (x0 + 0.5f * dt * k1_0) + b_val0 * u0;
            float k2_1 = a1 * (x1 + 0.5f * dt * k1_1) + b_val1 * u1;

            float k3_0 = a0 * (x0 + 0.5f * dt * k2_0) + b_val0 * u0;
            float k3_1 = a1 * (x1 + 0.5f * dt * k2_1) + b_val1 * u1;

            float k4_0 = a0 * (x0 + dt * k3_0) + b_val0 * u0;
            float k4_1 = a1 * (x1 + dt * k3_1) + b_val1 * u1;

            x0 += (dt / 6.0f) * (k1_0 + 2.0f * k2_0 + 2.0f * k3_0 + k4_0);
            x1 += (dt / 6.0f) * (k1_1 + 2.0f * k2_1 + 2.0f * k3_1 + k4_1);

            int out_idx = (b * seq_len + t) * STATE_DIM;
            X_out[out_idx + d0] = x0;
            X_out[out_idx + d1] = x1;
        }
    }
}

extern "C" void launch_fused_blackwell_bit_ssm_ode_solver(
    const uint8_t* Bitplane_U,
    const float* A_diag,
    const float* B_vec,
    const float* Scale_LUT,
    float* X_out,
    int batch_size,
    int seq_len,
    float dt,
    cudaStream_t stream
) {
    int threads_per_block = 128; // 4 warps per block
    int warps_per_block = threads_per_block / WARP_SIZE;
    int num_blocks = (batch_size + warps_per_block - 1) / warps_per_block;
    if (num_blocks > 65535) num_blocks = 65535;

    fused_blackwell_bit_ssm_ode_solver_kernel<<<num_blocks, threads_per_block, 0, stream>>>(
        Bitplane_U, A_diag, B_vec, Scale_LUT, X_out, batch_size, seq_len, dt
    );
}
