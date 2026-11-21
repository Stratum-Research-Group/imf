// hardware/tb_imf_lie_polytope_router.sv
`timescale 1ns / 1ps

module tb_imf_lie_polytope_router;
    localparam int DIM = 8;
    localparam int DATA_WIDTH = 16;
    localparam int NUM_ROOTS = 240;

    logic clk;
    logic rst_n;
    logic valid_in;
    logic signed [DATA_WIDTH-1:0] state_in [DIM];
    logic signed [DATA_WIDTH-1:0] weight_matrix [DIM][DIM];

    logic valid_out;
    logic signed [DATA_WIDTH-1:0] state_out [DIM];
    logic [$clog2(NUM_ROOTS)-1:0] best_root_idx;
    logic signed [DATA_WIDTH*2-1:0] best_inner_prod;

    imf_lie_polytope_router #(
        .DIM(DIM),
        .DATA_WIDTH(DATA_WIDTH),
        .NUM_ROOTS(NUM_ROOTS)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .valid_in(valid_in),
        .state_in(state_in),
        .weight_matrix(weight_matrix),
        .valid_out(valid_out),
        .state_out(state_out),
        .best_root_idx(best_root_idx),
        .best_inner_prod(best_inner_prod)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;
        valid_in = 0;
        for (int i=0; i<DIM; i++) begin
            state_in[i] = 16'sh0100; // 1.0 in Q8.8
            for (int j=0; j<DIM; j++) begin
                weight_matrix[i][j] = (i == j) ? 16'sh0100 : 16'sh0010;
            end
        end

        #20 rst_n = 1;
        #10 valid_in = 1;
        #10 valid_in = 0;

        #50;
        $display("[✓] SystemVerilog Coprocessor Testbench completed: valid_out=%b, root_idx=%d", valid_out, best_root_idx);
        $finish;
    end
endmodule
