# OpenLane Configuration for tt_um_imf_orthoplex_tile
# Target PDK: SkyWater 130nm High-Density (sky130_fd_sc_hd)

set ::env(PDK) "sky130A"
set ::env(STD_CELL_LIBRARY) "sky130_fd_sc_hd"

set ::env(DESIGN_NAME) "tt_um_imf_orthoplex_tile"
set ::env(VERILOG_FILES) [list \
    "$::env(DESIGN_DIR)/../../rtl/tt_um_imf_orthoplex_tile.v" \
    "$::env(DESIGN_DIR)/../../rtl/orthoplex_pe.v" \
    "$::env(DESIGN_DIR)/../../rtl/dual_vortex_crossbar.v" \
]

# Clock Configuration (50 MHz target)
set ::env(CLOCK_PORT) "clk"
set ::env(CLOCK_PERIOD) "20.0"

# Silicon Footprint Constraints (TinyTapeout 1x1 Standard Slot: 160um x 100um)
set ::env(FP_SIZING) "absolute"
set ::env(DIE_AREA) "0 0 160 100"
set ::env(CORE_AREA) "10 10 150 90"
set ::env(PL_TARGET_DENSITY) "0.45"

# Routing Layers
set ::env(RT_MAX_LAYER) "met4"
set ::env(RT_MIN_LAYER) "met1"

# DRC and Antennas
set ::env(RUN_KLAYOUT_DRC) 1
set ::env(RUN_MAGIC_DRC) 1
set ::env(RUN_LVS) 1
set ::env(QUIT_ON_HOLD_VIOLATIONS) 1
set ::env(QUIT_ON_SETUP_VIOLATIONS) 1
