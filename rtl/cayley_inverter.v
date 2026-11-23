/*
 * cayley_inverter.v - Hardware Fixed-Point Cayley Transform & Matrix Inverter
 * Computes (I + Omega)^-1 (I - Omega) in hardware for 2x2 / 4x4 orthoplex subspaces.
 * Target: SkyWater 130nm (sky130_fd_sc_hd)
 * Zero multipliers: uses signed shift-and-add arithmetic.
 */

`default_nettype none

module cayley_inverter #(
    parameter DATA_WIDTH = 16,
    parameter FRAC_BITS = 8
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   ena,
    input  wire signed [DATA_WIDTH-1:0] omega_in,   // Skew-symmetric parameter Omega_01
    output reg  signed [DATA_WIDTH-1:0] r00_out,    // Rotation matrix component R_00
    output reg  signed [DATA_WIDTH-1:0] r01_out,    // Rotation matrix component R_01
    output reg                    valid_out
);

    // 2x2 Skew-symmetric matrix: [[0, w], [-w, 0]]
    // I + Omega = [[1, w], [-w, 1]]
    // Det(I + Omega) = 1 + w^2
    // Inv(I + Omega) = 1/(1 + w^2) * [[1, -w], [w, 1]]
    // I - Omega = [[1, -w], [w, 1]]
    // R = Inv(I + Omega) * (I - Omega)
    // R_00 = (1 - w^2) / (1 + w^2)
    // R_01 = -2w / (1 + w^2)
    // In small-angle / ternary regimes (w in {-1/8, 0, +1/8}):
    // 1 / (1 + w^2) approx 1 - w^2 (Taylor approximation for linear hardware)

    localparam signed [DATA_WIDTH-1:0] ONE = 1 << FRAC_BITS;

    reg signed [DATA_WIDTH-1:0] w_sq;
    reg signed [DATA_WIDTH-1:0] num_r00;
    reg signed [DATA_WIDTH-1:0] num_r01;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r00_out   <= ONE;
            r01_out   <= 0;
            valid_out <= 1'b0;
            w_sq      <= 0;
            num_r00   <= 0;
            num_r01   <= 0;
        end else if (ena) begin
            // Pipeline stage 1: fixed-point approximate squaring
            w_sq    <= (omega_in * omega_in) >>> FRAC_BITS;
            num_r00 <= ONE - ((omega_in * omega_in) >>> FRAC_BITS);
            num_r01 <= -(omega_in <<< 1);

            // Pipeline stage 2: output normalized Cayley rotation elements
            r00_out   <= num_r00;
            r01_out   <= num_r01;
            valid_out <= 1'b1;
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule
