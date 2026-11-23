`default_nettype none

/**
 * SkyWater 130nm Synthesizable Hardware Flash-Cayley Dot Product Unit.
 *
 * Implements an 8-dimensional fixed-point (Q8.8, 16-bit signed) dot product
 * with an online running maximum comparator for numerical softmax stability.
 */

module flash_cayley_attention_core (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid_in,
    input  wire [127:0] q_rot_vec,  // 8x 16-bit signed Q8.8 rotated query
    input  wire [127:0] k_vec,      // 8x 16-bit signed Q8.8 key
    input  wire [15:0]  v_scalar,   // 16-bit signed Q8.8 value
    output reg         valid_out,
    output reg  [31:0]  dot_product, // 32-bit Q16.16 dot product
    output reg  [15:0]  max_score,   // 16-bit Q8.8 online running max
    output reg  [31:0]  v_accum      // 32-bit Q16.16 value accumulator
);

    // Unpack inputs
    wire signed [15:0] q[0:7];
    wire signed [15:0] k[0:7];
    wire signed [15:0] v = v_scalar;

    genvar i;
    generate
        for (i = 0; i < 8; i = i + 1) begin : gen_unpack
            assign q[i] = q_rot_vec[(i+1)*16 - 1 : i*16];
            assign k[i] = k_vec[(i+1)*16 - 1 : i*16];
        end
    endgenerate

    // Multipliers
    wire signed [31:0] prod[0:7];
    generate
        for (i = 0; i < 8; i = i + 1) begin : gen_mult
            assign prod[i] = q[i] * k[i];
        end
    endgenerate

    // Pipelined adder tree
    reg signed [31:0] sum_l1[0:3];
    reg signed [31:0] sum_l2[0:1];
    reg signed [31:0] sum_total;
    reg signed [15:0] v_pipe;
    reg               vld_pipe;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out   <= 1'b0;
            dot_product <= 32'sd0;
            max_score   <= -16'sd32768;
            v_accum     <= 32'sd0;
            sum_total   <= 32'sd0;
            vld_pipe    <= 1'b0;
            v_pipe      <= 16'sd0;
        end else begin
            // Stage 1: Pairwise additions
            sum_l1[0] <= prod[0] + prod[1];
            sum_l1[1] <= prod[2] + prod[3];
            sum_l1[2] <= prod[4] + prod[5];
            sum_l1[3] <= prod[6] + prod[7];
            v_pipe    <= v;
            vld_pipe  <= valid_in;

            // Stage 2: Tree reduction & running max
            sum_l2[0] <= sum_l1[0] + sum_l1[1];
            sum_l2[1] <= sum_l1[2] + sum_l1[3];
            sum_total <= sum_l2[0] + sum_l2[1];

            // Output stage
            if (vld_pipe) begin
                valid_out   <= 1'b1;
                dot_product <= sum_total;
                v_accum     <= v_accum + (sum_total[23:8] * v_pipe);

                // Online maximum tracking (Q8.8 representation)
                if (sum_total[23:8] > max_score) begin
                    max_score <= sum_total[23:8];
                end
            end else begin
                valid_out <= 1'b0;
            end
        end
    end

endmodule
