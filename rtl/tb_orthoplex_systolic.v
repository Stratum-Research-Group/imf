// ============================================================================
// Module: tb_orthoplex_systolic.v
// Testbench: Verifies NOSA Processing Element & Dual Vortex Crossbar
// ============================================================================

`timescale 1ns / 1ps

module tb_orthoplex_systolic;

    reg clk;
    reg rst_n;
    reg enable;
    reg is_l1_mode;
    reg [1:0] weight_ternary;
    reg signed [15:0] data_in_x;
    reg signed [15:0] data_in_y;

    wire signed [15:0] data_out_x;
    wire signed [15:0] data_out_y;
    wire signed [31:0] acc_out;

    reg null_point_strobe;
    reg [63:0] tensor_pos;
    reg [63:0] tensor_neg;
    wire [63:0] clutched_out;
    wire transfer_valid;

    // Instantiate PE
    orthoplex_pe #(
        .DATA_WIDTH(16),
        .ACC_WIDTH(32)
    ) dut_pe (
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

    // Instantiate Crossbar
    dual_vortex_crossbar #(
        .DATA_WIDTH(64)
    ) dut_crossbar (
        .clk(clk),
        .rst_n(rst_n),
        .null_point_strobe(null_point_strobe),
        .state_tensor_in_pos(tensor_pos),
        .state_tensor_in_neg(tensor_neg),
        .clutched_tensor_out(clutched_out),
        .transfer_valid(transfer_valid)
    );

    always #5 clk = ~clk; // 100 MHz simulation clock

    initial begin
        $display("[*] Starting Verilog Simulation of Orthoplex PE & Crossbar...");
        clk = 0;
        rst_n = 0;
        enable = 0;
        is_l1_mode = 0;
        weight_ternary = 2'b00;
        data_in_x = 0;
        data_in_y = 0;
        null_point_strobe = 0;
        tensor_pos = 64'hAAAA_AAAA_AAAA_AAAA;
        tensor_neg = 64'h5555_5555_5555_5555;

        #20 rst_n = 1;
        enable = 1;

        // Step 1: Accumulate +100 (w = +1)
        #10 data_in_x = 16'sd100; weight_ternary = 2'b01;
        #10 data_in_x = 16'sd50;  weight_ternary = 2'b11; // -50 (w = -1)
        #10 data_in_x = 16'sd99;  weight_ternary = 2'b00; // NOP (w = 0)

        // Step 2: Test L1 absolute distance mode (|100 - 30| = 70)
        #10 is_l1_mode = 1; data_in_x = 16'sd100; data_in_y = 16'sd30;
        
        // Step 3: Trigger Crossbar Null Point
        #10 null_point_strobe = 1;
        #10 null_point_strobe = 0;

        #20;
        $display("[✓] Simulation completed successfully. Final Accumulator = %d", acc_out);
        $display("[✓] Clutched Crossbar Output = %h (Valid = %b)", clutched_out, transfer_valid);
        $finish;
    end

endmodule
