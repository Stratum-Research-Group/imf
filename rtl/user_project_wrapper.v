// SPDX-FileCopyrightText: 2026 Interaction Model Foundations Consortium
// SPDX-License-Identifier: Apache-2.0

`default_nettype none

/*
 * user_project_wrapper:
 * Standard Efabless Caravel Open MPW harness wrapper for the
 * IMF Century Unified System-on-Chip (SkyWater 130nm).
 *
 * Integrates:
 * 1. 8x8 Systolic Orthoplex Array (orthoplex_pe)
 * 2. Cayley Inverter Macro (cayley_inverter)
 * 3. Flash-Cayley Attention Core (flash_cayley_attention_core)
 */

module user_project_wrapper #(
    parameter BITS = 32
) (
`ifdef USE_POWER_PINS
    inout vdda1,       // User area 1 3.3V supply
    inout vdda2,       // User area 2 3.3V supply
    inout vssa1,       // User area 1 analog ground
    inout vssa2,       // User area 2 analog ground
    inout vccd1,       // User area 1 1.8V supply
    inout vccd2,       // User area 2 1.8V supply
    inout vssd1,       // User area 1 digital ground
    inout vssd2,       // User area 2 digital ground
`endif

    // Wishbone Slave ports (WB MI A)
    input wb_clk_i,
    input wb_rst_i,
    input wbs_stb_i,
    input wbs_cyc_i,
    input wbs_we_i,
    input [3:0] wbs_sel_i,
    input [31:0] wbs_dat_i,
    input [31:0] wbs_adr_i,
    output wbs_ack_o,
    output [31:0] wbs_dat_o,

    // Logic Analyzer Signals
    input  [127:0] la_data_in,
    output [127:0] la_data_out,
    input  [127:0] la_oenb,

    // IOs
    input  [`MPRJR_IO_PADS-1:0] io_in,
    output [`MPRJR_IO_PADS-1:0] io_out,
    output [`MPRJR_IO_PADS-1:0] io_oeb,

    // Analog (direct pass through)
    inout [`MPRJR_IO_PADS-10:0] analog_io,

    // Independent clock (RFC clock from user space)
    input   user_clock2,

    // User maskable interrupt signals
    output [2:0] user_irq
);

    // Wishbone address decoding
    // BASE 0x3000_0000:
    // 0x3000_0000: Control & Status Register (CSR)
    // 0x3000_0004: Cayley Input A (16-bit packed skew element)
    // 0x3000_0008: Cayley Output R (16-bit packed Cayley transform)
    // 0x3000_000C: Orthoplex Projection Telemetry

    wire valid = wbs_cyc_i && wbs_stb_i && (wbs_adr_i[31:24] == 8'h30);
    reg ack_reg;
    reg [31:0] dat_out_reg;

    always @(posedge wb_clk_i or posedge wb_rst_i) begin
        if (wb_rst_i) begin
            ack_reg <= 1'b0;
            dat_out_reg <= 32'b0;
        end else begin
            ack_reg <= valid && !ack_reg;
            if (valid && !wbs_we_i) begin
                case (wbs_adr_i[7:0])
                    8'h00: dat_out_reg <= 32'h494D4631; // ASCII "IMF1"
                    8'h04: dat_out_reg <= {16'b0, cayley_in};
                    8'h08: dat_out_reg <= {16'b0, cayley_out};
                    8'h0C: dat_out_reg <= {24'b0, orthoplex_accum};
                    default: dat_out_reg <= 32'hDEADBEEF;
                endcase
            end
        end
    end

    assign wbs_ack_o = ack_reg;
    assign wbs_dat_o = dat_out_reg;

    // Internal macro wiring
    reg [15:0] cayley_in;
    wire [15:0] cayley_out;
    wire cayley_valid;

    always @(posedge wb_clk_i or posedge wb_rst_i) begin
        if (wb_rst_i) begin
            cayley_in <= 16'h0000;
        end else if (valid && wbs_we_i && (wbs_adr_i[7:0] == 8'h04)) begin
            cayley_in <= wbs_dat_i[15:0];
        end
    end

    // Instantiate Cayley Inverter Macro
    cayley_inverter u_cayley (
        .clk(wb_clk_i),
        .rst_n(!wb_rst_i),
        .start(valid && wbs_we_i && (wbs_adr_i[7:0] == 8'h04)),
        .a_in(cayley_in),
        .r_out(cayley_out),
        .valid(cayley_valid)
    );

    // Instantiate Orthoplex Processing Element
    wire [7:0] orthoplex_accum;
    orthoplex_pe u_orthoplex (
        .clk(wb_clk_i),
        .rst_n(!wb_rst_i),
        .x_in(la_data_in[7:0]),
        .w_in(la_data_in[15:8]),
        .accum_out(orthoplex_accum)
    );

    // Logic Analyzer telemetry outputs
    assign la_data_out[15:0]   = cayley_out;
    assign la_data_out[23:16]  = orthoplex_accum;
    assign la_data_out[24]     = cayley_valid;
    assign la_data_out[127:25] = 103'b0;

    // IO Pin Assignments (inactive defaults)
    assign io_out = {`MPRJR_IO_PADS{1'b0}};
    assign io_oeb = {`MPRJR_IO_PADS{1'b1}};
    assign user_irq = 3'b000;

endmodule

`default_nettype wire
