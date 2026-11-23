"""
IMF Multi-Macro Physical LEF / DEF Pin-Placement & Routing Generator.
Generates industry-standard physical layout exchange (.lef) and design exchange (.def)
files for the 3-macro stitched SkyWater 130nm ASIC tile.
"""

import os
from pathlib import Path

OPENLANE_DIR = Path("rtl/openlane_bundle")
LEF_DIR = OPENLANE_DIR / "lef"
DEF_DIR = OPENLANE_DIR / "def"

def generate_macro_lef_def():
    print("=" * 80)
    print("   IMF MULTI-MACRO LEF / DEF PHYSICAL PIN-PLACEMENT GENERATOR")
    print("   Process: SkyWater 130nm | Die Size: 180um x 180um (32,400 um^2)")
    print("=" * 80)

    LEF_DIR.mkdir(parents=True, exist_ok=True)
    DEF_DIR.mkdir(parents=True, exist_ok=True)

    lef_file = LEF_DIR / "imf_century_unified_soc_top.lef"
    def_file = DEF_DIR / "imf_century_unified_soc_top.def"

    # Generate LEF
    lef_content = """VERSION 5.8 ;
BUSBITCHARS "[]" ;
DIVIDERCHAR "/" ;

MACRO imf_century_unified_soc_top
  CLASS BLOCK ;
  ORIGIN 0.000 0.000 ;
  FOREIGN imf_century_unified_soc_top 0.000 0.000 ;
  SIZE 180.000 BY 180.000 ;
  SYMMETRY X Y R90 ;

  PIN clk
    DIRECTION INPUT ;
    USE SIGNAL ;
    PORT
      LAYER met2 ;
      RECT 10.000 0.000 10.400 1.200 ;
    END
  END clk

  PIN rst_n
    DIRECTION INPUT ;
    USE SIGNAL ;
    PORT
      LAYER met2 ;
      RECT 20.000 0.000 20.400 1.200 ;
    END
  END rst_n

  PIN data_in[7:0]
    DIRECTION INPUT ;
    USE SIGNAL ;
    PORT
      LAYER met3 ;
      RECT 0.000 30.000 1.200 45.000 ;
    END
  END data_in[7:0]

  PIN data_out[7:0]
    DIRECTION OUTPUT ;
    USE SIGNAL ;
    PORT
      LAYER met3 ;
      RECT 178.800 30.000 180.000 45.000 ;
    END
  END data_out[7:0]

  PIN vccd1
    DIRECTION INOUT ;
    USE POWER ;
    PORT
      LAYER met4 ;
      RECT 0.000 170.000 180.000 178.000 ;
    END
  END vccd1

  PIN vssd1
    DIRECTION INOUT ;
    USE GROUND ;
    PORT
      LAYER met4 ;
      RECT 0.000 2.000 180.000 10.000 ;
    END
  END vssd1

  OBS
    LAYER met1 ;
    RECT 0.000 0.000 180.000 180.000 ;
    LAYER met2 ;
    RECT 0.000 0.000 180.000 180.000 ;
  END
END imf_century_unified_soc_top
END LIBRARY
"""

    with open(lef_file, "w") as f:
        f.write(lef_content)

    # Generate DEF
    def_content = """VERSION 5.8 ;
DIVIDERCHAR "/" ;
BUSBITCHARS "[]" ;
DESIGN imf_century_unified_soc_top ;
UNITS DISTANCE MICRONS 1000 ;

DIEAREA ( 0 0 ) ( 180000 180000 ) ;

COMPONENTS 3 ;
- macro_systolic_orthoplex orthoplex_pe_array
  + PLACED ( 15000 15000 ) N ;
- macro_cayley_inverter cayley_inverter_core
  + PLACED ( 95000 15000 ) N ;
- macro_flash_cayley_attention flash_cayley_core
  + PLACED ( 30000 95000 ) N ;
END COMPONENTS

PINS 6 ;
- clk + NET clk + DIRECTION INPUT + USE SIGNAL
  + LAYER met2 ( 0 0 ) ( 400 1200 ) + PLACED ( 10000 0 ) N ;
- rst_n + NET rst_n + DIRECTION INPUT + USE SIGNAL
  + LAYER met2 ( 0 0 ) ( 400 1200 ) + PLACED ( 20000 0 ) N ;
- data_in[7:0] + NET data_in + DIRECTION INPUT + USE SIGNAL
  + LAYER met3 ( 0 0 ) ( 1200 15000 ) + PLACED ( 0 30000 ) E ;
- data_out[7:0] + NET data_out + DIRECTION OUTPUT + USE SIGNAL
  + LAYER met3 ( 0 0 ) ( 1200 15000 ) + PLACED ( 178800 30000 ) W ;
- vccd1 + NET vccd1 + DIRECTION INOUT + USE POWER
  + LAYER met4 ( 0 0 ) ( 180000 8000 ) + PLACED ( 0 170000 ) N ;
- vssd1 + NET vssd1 + DIRECTION INOUT + USE GROUND
  + LAYER met4 ( 0 0 ) ( 180000 8000 ) + PLACED ( 0 2000 ) N ;
END PINS

NETS 4 ;
- clk ( PIN clk ) ( macro_systolic_orthoplex clk ) ( macro_cayley_inverter clk ) ( macro_flash_cayley_attention clk ) ;
- rst_n ( PIN rst_n ) ( macro_systolic_orthoplex rst_n ) ( macro_cayley_inverter rst_n ) ( macro_flash_cayley_attention rst_n ) ;
- inter_macro_systolic_to_cayley ( macro_systolic_orthoplex data_out ) ( macro_cayley_inverter data_in ) ;
- inter_macro_cayley_to_flash ( macro_cayley_inverter data_out ) ( macro_flash_cayley_attention data_in ) ;
END NETS

END DESIGN
"""

    with open(def_file, "w") as f:
        f.write(def_content)

    print(f"[✓] Physical Layout LEF Exported: {lef_file}")
    print(f"[✓] Physical Placement DEF Exported: {def_file}")
    print("=" * 80)

if __name__ == "__main__":
    generate_macro_lef_def()
