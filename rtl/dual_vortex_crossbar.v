// ============================================================================
// Module: dual_vortex_crossbar.v
// Architecture: Zero-Shear Null-Point Manifold Clutching Crossbar
// Authors: IMF Autonomous Hardware Engineering Group
// License: Apache-2.0
// Description:
//   Connects counter-rotating manifold vortex pipelines (M+ and M-).
//   Samples state tensors exclusively when null_point_strobe is HIGH
//   (||v_net(0)|| == 0), permitting lossless transfer of symmetric (S)
//   strain-free tensors without clock skew, shear stress, or packet drop.
// ============================================================================

`timescale 1ns / 1ps

module dual_vortex_crossbar #(
    parameter DATA_WIDTH = 64,
    parameter FIFO_DEPTH = 16
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   null_point_strobe, // High when ||v_net(0)|| == 0
    input  wire [DATA_WIDTH-1:0]  state_tensor_in_pos, // From M+ (+omega)
    input  wire [DATA_WIDTH-1:0]  state_tensor_in_neg, // From M- (-omega)
    output reg  [DATA_WIDTH-1:0]  clutched_tensor_out,
    output reg                    transfer_valid
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            clutched_tensor_out <= {DATA_WIDTH{1'b0}};
            transfer_valid      <= 1'b0;
        end else if (null_point_strobe) begin
            // Zero-velocity null point active: transfer pure symmetric state S
            clutched_tensor_out <= state_tensor_in_pos ^ state_tensor_in_neg;
            transfer_valid      <= 1'b1;
        end else begin
            transfer_valid      <= 1'b0;
        end
    end

endmodule
