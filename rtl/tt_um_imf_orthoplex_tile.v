// ============================================================================
// Module: tt_um_imf_orthoplex_tile.v
// Tiny Tapeout / SkyWater 130nm Top-Level Wrapper
// Authors: IMF Autonomous Hardware Engineering Group
// License: Apache-2.0
// Description:
//   Standard 8-in, 8-out, 8-bidirectional pin interface conforming to
//   TinyTapeout digital submission standards:
//     ui_in[0]    : enable
//     ui_in[1]    : is_l1_mode
//     ui_in[3:2]  : weight_ternary (2'b00: 0, 2'b01: +1, 2'b11: -1)
//     ui_in[4]    : null_point_strobe
//     ui_in[7:5]  : reserved / config
//     uio_in[7:0] : data_in_x (8-bit signed)
//     uo_out[7:0] : lower 8 bits of accumulator / clutched tensor
// ============================================================================

`timescale 1ns / 1ps
`default_nettype none

module tt_um_imf_orthoplex_tile (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // will go high when the design is enabled
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

    wire enable             = ui_in[0] & ena;
    wire is_l1_mode         = ui_in[1];
    wire [1:0] weight_ternary = ui_in[3:2];
    wire null_point_strobe  = ui_in[4];

    wire signed [7:0] data_in_x = uio_in;
    wire signed [7:0] data_in_y = 8'sd0;

    wire signed [7:0] data_out_x;
    wire signed [7:0] data_out_y;
    wire signed [15:0] acc_out;

    orthoplex_pe #(
        .DATA_WIDTH(8),
        .ACC_WIDTH(16)
    ) pe_inst (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .is_l1_mode(is_l1_mode),
        .weight_ternary(weight_ternary),
        .data_in_x(data_in_x),
        .data_in_y(data_in_y),
        .data_out_x(data_out_x),
        .data_out_y(data_out_y),
        .acc_out(acc_out)
    );

    wire [7:0] clutched_out;
    wire transfer_valid;

    dual_vortex_crossbar #(
        .DATA_WIDTH(8)
    ) crossbar_inst (
        .clk(clk),
        .rst_n(rst_n),
        .null_point_strobe(null_point_strobe),
        .state_tensor_in_pos(ui_in),
        .state_tensor_in_neg(uio_in),
        .clutched_tensor_out(clutched_out),
        .transfer_valid(transfer_valid)
    );

    // Output mapping
    assign uo_out  = null_point_strobe ? clutched_out : acc_out[7:0];
    assign uio_out = acc_out[15:8];
    assign uio_oe  = 8'h00; // All bidirectional pins configured as inputs

endmodule
