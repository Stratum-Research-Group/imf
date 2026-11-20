"""
VLSI Silicon Hardware, Proteomics & Cleavage Biomedicine, and Computational Neuroscience Synthesizer (IMF).
Covers advanced specialized disciplines for graduate-level engineering and biophysics:
1. VLSI & Hardware Circuit Types:
   - Verilog & SystemVerilog RTL synthesizable digital design (pipelined MAC, finite state machines, clock gating).
   - CMOS Analog & Mixed-Signal IC design (differential pair, current mirrors, folded cascode, RC parasitics).
   - SPICE netlists (BSIM-CMG FinFET models, transit frequency f_T, phase margins).
2. Proteomics & Cleavage Biomedicine:
   - Protease cleavage mechanics (TEV protease ENLYFQ|G, Thrombin LVPR|GS, Enterokinase DDDDK|).
   - Peptide backbone dihedral Ramachandran angles (phi, psi), secondary structure (alpha-helix, beta-sheet).
   - Post-Translational Modifications (PTMs): Ser/Thr phosphorylation, Lys ubiquitination, Asn N-linked glycosylation.
   - Antibody CDR paratope-epitope binding interfaces.
3. Computational Neuroscience & Neural Dynamics:
   - Hodgkin-Huxley biophysical action potential conductance equations (g_Na m^3 h, g_K n^4, g_L).
   - Leaky Integrate-and-Fire (LIF) neuromorphic spiking models (tau_m dV/dt = -(V - V_rest) + R*I).
   - Spike-Timing-Dependent Plasticity (STDP) hebbian learning windows (delta_w = A_+ exp(-delta_t / tau_+)).
   - Cable theory for dendritic electrotonic attenuation (lambda = sqrt(r_m / r_i)).
"""

from typing import List, Tuple
import random

VLSI_BIOMED_NEURO_DOMAINS: List[str] = [
    "vlsi_systemverilog_digital_rtl",    # Synthesizable RTL, clock domain crossing, pipelined datapath, AXI-Stream
    "vlsi_analog_spice_circuit_ic",     # Differential amplifiers, current mirrors, SPICE transient/AC analysis, FinFETs
    "biomed_proteomics_protease_cleave",# Protease cleavage recognition motifs, peptide synthesis, PTMs, Ramachandran
    "biomed_structural_antibody_cdr",   # Immunoglobulin CDR loops, paratope-epitope interfaces, affinity maturation
    "neuro_biophysical_hodgkin_huxley", # Hodgkin-Huxley voltage-gated ion channels, Nernst reversal potentials
    "neuro_spiking_stdp_neuromorphic",  # Leaky integrate-and-fire (LIF), STDP plasticity, dendritic cable theory
]

class VLSIBiomedNeuroSynthesizer:
    def __init__(self, seed: int = 101):
        self.rng = random.Random(seed)

    def generate_systemverilog_vlsi(self) -> str:
        samples = [
            ("// SystemVerilog Synthesizable RTL: Pipelined Multiply-Accumulate (MAC) Unit\n"
             "module pipelined_mac #(\n"
             "    parameter int DATA_WIDTH = 16,\n"
             "    parameter int ACCUM_WIDTH = 40\n"
             ") (\n"
             "    input  logic                   clk,\n"
             "    input  logic                   rst_n,\n"
             "    input  logic                   valid_in,\n"
             "    input  logic signed [DATA_WIDTH-1:0]  a_in,\n"
             "    input  logic signed [DATA_WIDTH-1:0]  b_in,\n"
             "    output logic                   valid_out,\n"
             "    output logic signed [ACCUM_WIDTH-1:0] accum_out\n"
             ");\n"
             "    // Pipeline Stage 1: Registered Multiplier\n"
             "    logic signed [2*DATA_WIDTH-1:0] mult_reg;\n"
             "    logic valid_p1;\n"
             "    always_ff @(posedge clk or negedge rst_n) begin\n"
             "        if (!rst_n) begin\n"
             "            mult_reg  <= '0;\n"
             "            valid_p1  <= 1'b0;\n"
             "        end else if (valid_in) begin\n"
             "            mult_reg  <= a_in * b_in;\n"
             "            valid_p1  <= 1'b1;\n"
             "        end else begin\n"
             "            valid_p1  <= 1'b0;\n"
             "        end\n"
             "    end\n"
             "    // Pipeline Stage 2: Accumulator\n"
             "    always_ff @(posedge clk or negedge rst_n) begin\n"
             "        if (!rst_n) begin\n"
             "            accum_out <= '0;\n"
             "            valid_out <= 1'b0;\n"
             "        end else if (valid_p1) begin\n"
             "            accum_out <= accum_out + mult_reg;\n"
             "            valid_out <= 1'b1;\n"
             "        end else begin\n"
             "            valid_out <= 1'b0;\n"
             "        end\n"
             "    end\n"
             "endmodule\n"),
            
            ("* SPICE Analog Netlist: CMOS Cascode Current Mirror with High Output Impedance\n"
             ".SUBCKT CASCODE_MIRROR VDD VSS IREF IOUT\n"
             "M1 N1 N1 VSS VSS NMOS_16NM W=320n L=16n\n"
             "M2 IREF N1 N2 VSS NMOS_16NM W=320n L=16n\n"
             "M3 IOUT N3 N4 VSS NMOS_16NM W=320n L=16n\n"
             "M4 N4 N1 VSS VSS NMOS_16NM W=320n L=16n\n"
             "* Small-Signal Output Resistance: R_out ~= g_m3 * r_o3 * r_o4\n"
             ".ENDS CASCODE_MIRROR\n")
        ]
        return self.rng.choice(samples)

    def generate_proteomics_biomed(self) -> str:
        samples = [
            ("# Proteomics & Protease Cleavage Engineering\n"
             "Target Fusion Protein: His6-MBP-TEV_site-RecombinantHumanKinase\n"
             "Canonical Cleavage Sequence: Tobacco Etch Virus (TEV) Protease Motif: Glu-Asn-Leu-Tyr-Phe-Gln-Gly/Ser (ENLYFQ|G)\n"
             "Cleavage Specificity:\n"
             "- P6 (Glu): Strict electrostatic contact with Arg50 of TEV protease catalytic pocket.\n"
             "- P3 (Leu) & P1 (Gln): Fits into hydrophobic S3 subsite and hydrogen-bonds with His46 in S1 pocket.\n"
             "- Scissile Bond: Peptide bond between Gln (P1) and Gly (P1').\n"
             "Enzyme Kinetics: Catalytic triad Cys151-His46-Asp81 executes nucleophilic attack on Gln carbonyl carbon, forming acyl-enzyme intermediate.\n"
             "Post-Cleavage Isolation: Subtractive Ni-NTA chromatography collects untagged recombinant kinase in flow-through.\n"),
            
            ("# Structural Immunology: Antibody CDR Paratope Engineering\n"
             "Immunoglobulin Variable Domain: Heavy (VH) & Light (VL) Chains\n"
             "Complementarity-Determining Regions: CDR-H1, CDR-H2, CDR-H3\n"
             "Structural Role of CDR-H3: Located at center of antigen-binding paratope, highest sequence and loop length diversity (8-25 amino acids).\n"
             "Canonical Base Structure: Hairpin stabilized by salt bridge between Arg94 and Asp101.\n"
             "Antigen Affinity Maturation: Somatic hypermutation introduces Tyr/Trp aromatic residues to mediate hydrophobic pi-pi stacking with viral spike protein epitope.\n")
        ]
        return self.rng.choice(samples)

    def generate_neuroscience(self) -> str:
        samples = [
            ("# Computational Neuroscience: Hodgkin-Huxley Biophysical Membrane Dynamics\n"
             "Membrane Current Equation:\n"
             "C_m * (dV/dt) = -g_Na * m^3 * h * (V - E_Na) - g_K * n^4 * (V - E_K) - g_L * (V - E_L) + I_inj\n\n"
             "Gating Variable Kinetics (alpha and beta rate functions):\n"
             "dm/dt = alpha_m(V) * (1 - m) - beta_m(V) * m\n"
             "dh/dt = alpha_h(V) * (1 - h) - beta_h(V) * h\n"
             "dn/dt = alpha_n(V) * (1 - n) - beta_n(V) * n\n\n"
             "Parameters at 6.3°C:\n"
             "C_m = 1.0 uF/cm^2, g_Na = 120 mS/cm^2, g_K = 36 mS/cm^2, g_L = 0.3 mS/cm^2\n"
             "Reversal Potentials: E_Na = +50 mV, E_K = -77 mV, E_L = -54.4 mV\n"),
            
            ("# Neuromorphic Computing: Spike-Timing-Dependent Plasticity (STDP)\n"
             "Synaptic Weight Update Rule: Δw = W(Δt), where Δt = t_post - t_pre\n"
             "1. Long-Term Potentiation (LTP for Δt > 0, pre fires before post):\n"
             "   Δw = A_+ * exp(-Δt / tau_+), with A_+ > 0, tau_+ ~= 20 ms\n"
             "2. Long-Term Depression (LTD for Δt < 0, post fires before pre):\n"
             "   Δw = -A_- * exp(Δt / tau_-), with A_- > 0, tau_- ~= 20 ms\n"
             "Dendritic Attenuation (Cable Equation):\n"
             "lambda * (d^2 V / dx^2) = tau_m * (dV/dt) + V, where space constant lambda = sqrt(r_m / r_i)\n")
        ]
        return self.rng.choice(samples)

    def generate_corpus(self, num_samples: int = 100) -> List[Tuple[str, str]]:
        corpus = []
        generators = [
            (self.generate_systemverilog_vlsi, "vlsi_systemverilog_digital_rtl"),
            (self.generate_proteomics_biomed, "biomed_proteomics_protease_cleave"),
            (self.generate_neuroscience, "neuro_biophysical_hodgkin_huxley")
        ]
        for _ in range(num_samples):
            fn, tag = self.rng.choice(generators)
            corpus.append((fn(), tag))
        return corpus


if __name__ == "__main__":
    syn = VLSIBiomedNeuroSynthesizer()
    c = syn.generate_corpus(3)
    print(f"[*] VLSI, Biomedicine & Neuroscience Synthesizer: {len(VLSI_BIOMED_NEURO_DOMAINS)} dedicated domains:")
    for d in VLSI_BIOMED_NEURO_DOMAINS:
        print(f"  - {d}")
    print("\nSamples:")
    for txt, tag in c:
        print(f"[{tag}] -> {txt[:180]}...\n")
