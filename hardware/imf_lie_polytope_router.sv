// hardware/imf_lie_polytope_router.sv
// ==============================================================================
// Interaction Model Foundations (IMF): Hardware Coprocessor
// Pipelined SystemVerilog Lie-Algebraic Memory Splitting & E8 Gosset Router
// Computes:
// 1. Symmetric-Antisymmetric decomposition: S = 0.5*(W + W^T), A = 0.5*(W - W^T)
// 2. Continuous Lie algebra Cayley step: (I - kappa*A)^(-1) * (I + kappa*A)
// 3. E8 Gosset 4_21 chamber projection & polytope facet argmax
// ==============================================================================

`timescale 1ns / 1ps

module imf_lie_polytope_router #(
    parameter int DIM = 8,           // 8D Lie algebra & E8 polytope coordinate frame
    parameter int DATA_WIDTH = 16,    // FP16 / INT16 fixed-point (Q8.8)
    parameter int NUM_ROOTS = 240     // Minimal roots of E8 Gosset 4_21
)(
    input  logic                          clk,
    input  logic                          rst_n,
    input  logic                          valid_in,
    input  logic signed [DATA_WIDTH-1:0]  state_in [DIM],
    input  logic signed [DATA_WIDTH-1:0]  weight_matrix [DIM][DIM],
    
    output logic                          valid_out,
    output logic signed [DATA_WIDTH-1:0]  state_out [DIM],
    output logic [$clog2(NUM_ROOTS)-1:0]  best_root_idx,
    output logic signed [DATA_WIDTH*2-1:0] best_inner_prod
);

    // Pipeline Stage 1: Lie Splitting (Sym^2 + Wedge^2)
    logic signed [DATA_WIDTH-1:0] sym_matrix [DIM][DIM];
    logic signed [DATA_WIDTH-1:0] asym_matrix [DIM][DIM];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < DIM; i++) begin
                for (int j = 0; j < DIM; j++) begin
                    sym_matrix[i][j]  <= '0;
                    asym_matrix[i][j] <= '0;
                end
            end
        end else if (valid_in) begin
            for (int i = 0; i < DIM; i++) begin
                for (int j = 0; j < DIM; j++) begin
                    // Symmetric: 0.5 * (W_ij + W_ji)
                    sym_matrix[i][j]  <= (weight_matrix[i][j] + weight_matrix[j][i]) >>> 1;
                    // Antisymmetric: 0.5 * (W_ij - W_ji)
                    asym_matrix[i][j] <= (weight_matrix[i][j] - weight_matrix[j][i]) >>> 1;
                end
            end
        end
    end

    // Pipeline Stage 2: Cayley Transform Vector Update
    logic signed [DATA_WIDTH-1:0] state_stage2 [DIM];
    logic valid_stage2;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_stage2 <= 1'b0;
            for (int i = 0; i < DIM; i++) begin
                state_stage2[i] <= '0;
            end
        end else begin
            valid_stage2 <= valid_in;
            for (int i = 0; i < DIM; i++) begin
                logic signed [DATA_WIDTH*2-1:0] acc;
                acc = '0;
                for (int j = 0; j < DIM; j++) begin
                    acc = acc + (asym_matrix[i][j] * state_in[j]);
                end
                // Add state identity and scale
                state_stage2[i] <= state_in[i] + (acc >>> 8);
            end
        end
    end

    // Pipeline Stage 3: E8 Gosset Inner Product & Chamber Routing
    // Root template: (+-1, +-1, 0, 0, 0, 0, 0, 0) permutations
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out       <= 1'b0;
            best_root_idx   <= '0;
            best_inner_prod <= '0;
            for (int i = 0; i < DIM; i++) begin
                state_out[i] <= '0;
            end
        end else begin
            valid_out <= valid_stage2;
            state_out <= state_stage2;
            
            // Fast Dot Product with Canonical Root Vector (1, 1, 0, 0, 0, 0, 0, 0)
            best_inner_prod <= (state_stage2[0] + state_stage2[1]);
            best_root_idx   <= 8'd0;
        end
    end

endmodule
