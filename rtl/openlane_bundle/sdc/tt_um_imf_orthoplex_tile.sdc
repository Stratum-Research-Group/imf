# Timing Constraints for tt_um_imf_orthoplex_tile (50 MHz)
current_design tt_um_imf_orthoplex_tile

create_clock -name clk -period 20.0 [get_ports clk]
set_clock_uncertainty 0.25 [get_clocks clk]
set_clock_transition 0.15 [get_clocks clk]

# Input / Output Delays
set_input_delay -max 4.0 -clock clk [get_ports {ui_in[*] uio_in[*] ena rst_n}]
set_output_delay -max 4.0 -clock clk [get_ports {uo_out[*] uio_out[*] uio_oe[*]}]
