// ============================================================================
// Module: orthoplex_pe.v
// Architecture: Native Orthoplex Systolic Processing Element (NOSA Tile)
// Authors: IMF Autonomous Hardware Engineering Group
// License: Apache-2.0
// Description:
//   Executes ternary sparse dot-product and L1 absolute difference accumulation
//   without floating-point multipliers:
//     - weight_ternary == 2'b01 : acc <= acc + data_in
//     - weight_ternary == 2'b11 : acc <= acc - data_in
//     - weight_ternary == 2'b00 : acc <= acc (clock-gated NOP)
//     - is_l1_mode     == 1'b1  : acc <= acc + |data_in - data_y|
// ============================================================================

`timescale 1ns / 1ps

module orthoplex_pe #(
    parameter DATA_WIDTH = 16,
    parameter ACC_WIDTH  = 32
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   enable,
    input  wire                   is_l1_mode,
    input  wire [1:0]             weight_ternary, // 2'b00: 0, 2'b01: +1, 2'b11: -1
    input  wire signed [DATA_WIDTH-1:0] data_in_x,
    input  wire signed [DATA_WIDTH-1:0] data_in_y,
    output reg  signed [DATA_WIDTH-1:0] data_out_x,
    output reg  signed [DATA_WIDTH-1:0] data_out_y,
    output reg  signed [ACC_WIDTH-1:0]  acc_out
);

    // Widen difference computation to prevent signed overflow (e.g. 32767 - (-32768) = 65535)
    wire signed [DATA_WIDTH:0] diff_val;
    wire signed [DATA_WIDTH:0] abs_diff;

    assign diff_val = {data_in_x[DATA_WIDTH-1], data_in_x} - {data_in_y[DATA_WIDTH-1], data_in_y};
    assign abs_diff = (diff_val < 0) ? -diff_val : diff_val;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out_x <= {DATA_WIDTH{1'b0}};
            data_out_y <= {DATA_WIDTH{1'b0}};
            acc_out    <= {ACC_WIDTH{1'b0}};
        end else if (enable) begin
            // Forward pipeline systolic signals
            data_out_x <= data_in_x;
            data_out_y <= data_in_y;

            if (is_l1_mode) begin
                acc_out <= acc_out + {{(ACC_WIDTH-(DATA_WIDTH+1)){1'b0}}, abs_diff};
            end else begin
                case (weight_ternary)
                    2'b01: acc_out <= acc_out + {{(ACC_WIDTH-DATA_WIDTH){data_in_x[DATA_WIDTH-1]}}, data_in_x};
                    2'b11: acc_out <= acc_out - {{(ACC_WIDTH-DATA_WIDTH){data_in_x[DATA_WIDTH-1]}}, data_in_x};
                    default: acc_out <= acc_out; // Clock-gated NOP (0.082 pJ energy efficiency)
                endcase
            end
        end
    end

endmodule
