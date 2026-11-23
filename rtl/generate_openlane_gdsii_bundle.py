"""
rtl/generate_openlane_gdsii_bundle.py
OpenLane Physical Layout Configuration & GDSII Tape-out Flow Bundle (Track 3).
Prepares complete ASIC hardening bundle for tt_um_imf_orthoplex_tile:
- config.tcl: Clock, density, routing layers, DRC, and power grids
- pin_order.cfg: Dedicated TinyTapeout pin routing
- sdc/tt_um_imf_orthoplex_tile.sdc: 50 MHz clock constraints and I/O delays
- Generates layout artifacts in rtl/openlane_bundle/
"""

import os
from pathlib import Path

BUNDLE_DIR = Path("rtl/openlane_bundle")
BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
SDC_DIR = BUNDLE_DIR / "sdc"
SDC_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_TCL = """# OpenLane Configuration for tt_um_imf_orthoplex_tile
# Target PDK: SkyWater 130nm High-Density (sky130_fd_sc_hd)

set ::env(PDK) "sky130A"
set ::env(STD_CELL_LIBRARY) "sky130_fd_sc_hd"

set ::env(DESIGN_NAME) "tt_um_imf_orthoplex_tile"
set ::env(VERILOG_FILES) [list \\
    "$::env(DESIGN_DIR)/../../rtl/tt_um_imf_orthoplex_tile.v" \\
    "$::env(DESIGN_DIR)/../../rtl/orthoplex_pe.v" \\
    "$::env(DESIGN_DIR)/../../rtl/dual_vortex_crossbar.v" \\
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
"""

PIN_ORDER_CFG = """# North Pins
ui_in.*

# South Pins
uo_out.*

# East Pins
uio_in.*
uio_out.*

# West Pins
uio_oe.*
clk
rst_n
ena
"""

SDC_CONSTRAINTS = """# Timing Constraints for tt_um_imf_orthoplex_tile (50 MHz)
current_design tt_um_imf_orthoplex_tile

create_clock -name clk -period 20.0 [get_ports clk]
set_clock_uncertainty 0.25 [get_clocks clk]
set_clock_transition 0.15 [get_clocks clk]

# Input / Output Delays
set_input_delay -max 4.0 -clock clk [get_ports {ui_in[*] uio_in[*] ena rst_n}]
set_output_delay -max 4.0 -clock clk [get_ports {uo_out[*] uio_out[*] uio_oe[*]}]
"""

def generate_bundle():
    print("=" * 80)
    print("  OPENLANE GDSII SILICON TAPE-OUT BUNDLE GENERATION (TRACK 3)")
    print("=" * 80)

    cfg_path = BUNDLE_DIR / "config.tcl"
    with open(cfg_path, "w") as f:
        f.write(CONFIG_TCL)
    print(f"[✓] Generated OpenLane Config:   {cfg_path}")

    pins_path = BUNDLE_DIR / "pin_order.cfg"
    with open(pins_path, "w") as f:
        f.write(PIN_ORDER_CFG)
    print(f"[✓] Generated Pin Order Map:     {pins_path}")

    sdc_path = SDC_DIR / "tt_um_imf_orthoplex_tile.sdc"
    with open(sdc_path, "w") as f:
        f.write(SDC_CONSTRAINTS)
    print(f"[✓] Generated SDC Constraints:   {sdc_path}")
    print("=" * 80)
    print(f"[✓] Tape-out bundle ready at {BUNDLE_DIR}")
    print("=" * 80)

if __name__ == "__main__":
    generate_bundle()
