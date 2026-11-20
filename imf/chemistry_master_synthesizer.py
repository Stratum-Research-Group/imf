"""
Chemistry & Molecular Sciences Master Synthesizer (IMF).
Covers the core subdisciplines of modern chemistry:
1. Organic Chemistry & Retrosynthesis:
   - Reaction mechanisms (electrophilic addition, nucleophilic aromatic substitution, Diels-Alder [4+2] cycloaddition).
   - Retrosynthetic disconnects, protecting groups (Boc, TBS, Fmoc).
2. Physical Chemistry & Thermodynamics:
   - Gibbs free energy (ΔG = ΔH - TΔS), Arrhenius kinetics (k = A e^{-E_a/RT}), transition state theory.
   - Nernst equation (E = E° - (RT/nF) ln Q), electrochemistry, Hess's Law.
3. Inorganic & Organometallic Chemistry:
   - Crystal Field & Ligand Field Theory (octahedral Δ_o, tetrahedral Δ_t, high-spin vs low-spin).
   - 18-electron rule, oxidative addition, migratory insertion, Suzuki/Heck cross-coupling catalytic cycles.
4. Analytical Chemistry & Spectroscopy:
   - 1H & 13C NMR chemical shifts (ppm, multiplicity, coupling constants J_ab).
   - FTIR functional group absorption bands, Mass Spectrometry (MS) fragmentation patterns (McLafferty rearrangement).
5. Computational Chemistry & Molecular Modeling:
   - Density Functional Theory (DFT B3LYP/6-31G*), Hartree-Fock self-consistent field, molecular mechanics forcefields (CHARMM, AMBER).
6. Biochemistry & Enzymology:
   - Michaelis-Menten kinetics (v = V_max [S] / (K_m + [S])), Lineweaver-Burk plots, competitive/allosteric inhibition.
"""

from typing import List, Tuple
import random

CHEMISTRY_EXPERT_DOMAINS: List[str] = [
    "chem_organic_retrosynthesis",        # Retrosynthetic analysis, synthetic route planning, reaction mechanisms
    "chem_physical_thermodynamics",      # Gibbs free energy, Arrhenius kinetics, activation energy, electrochemistry
    "chem_inorganic_organometallics",     # Ligand field theory, 18-electron rule, palladium cross-coupling catalysis
    "chem_analytical_spectroscopy",       # 1H/13C NMR shifts, FTIR stretches, mass spec fragmentation
    "chem_computational_dft_docking",     # Density functional theory, Hartree-Fock, molecular dynamics, ligand docking
    "chem_biochemistry_enzymology",       # Michaelis-Menten kinetics, transition state analogs, allosteric regulation
]

class ChemistryMasterSynthesizer:
    def __init__(self, seed: int = 101):
        self.rng = random.Random(seed)

    def generate_organic_retrosynthesis(self) -> str:
        samples = [
            ("# Organic Chemistry: Retrosynthetic Disconnection & Stereoselective Synthesis\n"
             "Target Molecule: (R)-2-amino-1-phenylethan-1-ol\n\n"
             "// Retrosynthetic Analysis:\n"
             "// Target <= Sharpless Asymmetric Dihydroxylation of Styrene <= Styrene\n"
             "// Step 1: AD-mix-beta dihydroxylation of styrene gives (R)-1-phenylethane-1,2-diol (ee > 96%).\n"
             "// Step 2: Selective tosylation of primary alcohol via TsCl/DMAP at -20°C gives (R)-2-hydroxy-2-phenylethyl 4-methylbenzenesulfonate.\n"
             "// Step 3: Azide displacement with NaN3 in DMF (inversion at secondary or retention at primary -> clean SN2 at primary C-1).\n"
             "// Step 4: Staudinger reduction (PPh3, H2O, THF) yields target with preserved (R) chiral stereocenter.\n"),
            
            ("# Reaction Mechanism: Diels-Alder [4+2] Concerted Cycloaddition\n"
             "Diene: Cyclopentadiene (s-cis conformation)\n"
             "Dienophile: Maleic anhydride (electron-poor)\n"
             "Stereochemical Outcome: Endo rule (secondary orbital interactions between anhydride carbonyl pi* and diene developing pi-orbitals).\n"
             "Frontier Molecular Orbitals (FMO): HOMO(diene) -> LUMO(dienophile) overlap.\n"
             "Product: cis-norbornene-5,6-endo-dicarboxylic anhydride.\n")
        ]
        return self.rng.choice(samples)

    def generate_physical_thermodynamics(self) -> str:
        samples = [
            ("# Physical Chemistry: Chemical Kinetics & Transition State Theory\n"
             "Eyring-Polanyi Equation for Unimolecular Reaction Rate:\n"
             "k = (k_B * T / h) * exp(-ΔG‡ / (R * T)) = (k_B * T / h) * exp(ΔS‡ / R) * exp(-ΔH‡ / (R * T))\n\n"
             "For a gas-phase dimerization with activation energy E_a = 78.4 kJ/mol at T = 298.15 K:\n"
             "ΔH‡ = E_a - 2*R*T = 78,400 - 2 * 8.314 * 298.15 = 73.44 kJ/mol\n"
             "A negative activation entropy (ΔS‡ < 0) indicates an associative transition state with reduced rotational degrees of freedom.\n"),
            
            ("# Electrochemistry & Nernst Potential\n"
             "Galvanic Cell: Zn(s) | Zn2+(0.05 M) || Cu2+(1.20 M) | Cu(s)\n"
             "Standard Potentials: E°(Zn2+/Zn) = -0.763 V, E°(Cu2+/Cu) = +0.340 V\n"
             "Standard Cell Potential: E°_cell = E°_cathode - E°_anode = 0.340 - (-0.763) = 1.103 V\n"
             "Reaction Quotient Q = [Zn2+] / [Cu2+] = 0.05 / 1.20 = 0.04167\n"
             "Cell Potential at 298.15 K: E_cell = E°_cell - (0.05916 / n) * log10(Q) = 1.103 - (0.05916 / 2) * log10(0.04167) = 1.144 V\n")
        ]
        return self.rng.choice(samples)

    def generate_inorganic_organometallics(self) -> str:
        samples = [
            ("# Organometallic Chemistry: Palladium-Catalyzed Suzuki-Miyaura Cross-Coupling\n"
             "Catalyst: Pd(PPh3)4 (precatalyst) -> Pd(0) active 14-electron complex Pd(PPh3)2\n"
             "Catalytic Cycle Steps:\n"
             "1. Oxidative Addition: Pd(0) inserts into Aryl Halide Ar-Br bond -> cis/trans-[Ar-Pd(II)(PPh3)2-Br] (16e- square planar).\n"
             "2. Transmetalation: Base (K2CO3/KOH) activates boronic acid Ar'-B(OH)2 into boronate [Ar'-B(OH)3]-; transfer of Ar' to Pd(II) displacing halide -> [Ar-Pd(II)(PPh3)2-Ar'].\n"
             "3. cis-trans Isomerization: Brings Ar and Ar' into mutual cis orientation.\n"
             "4. Reductive Elimination: Expels biaryl product Ar-Ar' and regenerates the active Pd(0) catalyst.\n"),
            
            ("# Inorganic Chemistry: Octahedral Crystal Field Theory & d-Electron Configurations\n"
             "Complex: [Fe(H2O)6]2+ vs [Fe(CN)6]4-\n"
             "Metal Ion: Fe(II) (d6 configuration)\n"
             "1. Weak-Field Ligand (H2O): High-spin configuration (t2g^4 eg^2), CFSE = -0.4 * Δ_o * 4 + 0.6 * Δ_o * 2 = -0.4 * Δ_o. Paramagnetic (4 unpaired electrons).\n"
             "2. Strong-Field Ligand (CN-): Low-spin configuration (t2g^6 eg^0), CFSE = -0.4 * Δ_o * 6 + 2P = -2.4 * Δ_o + 2P. Diamagnetic (0 unpaired electrons).\n")
        ]
        return self.rng.choice(samples)

    def generate_analytical_spectroscopy(self) -> str:
        samples = [
            ("# Analytical Chemistry: 1H NMR Structural Elucidation\n"
             "Empirical Formula: C4H8O2 (Degree of Unsaturation = 4 - 8/2 + 1 = 1 degree -> carbonyl or ring)\n"
             "Spectroscopic Resonances:\n"
             "- delta 1.25 (3H, t, J = 7.1 Hz): CH3 coupled to adjacent CH2\n"
             "- delta 2.05 (3H, s): Isolated CH3 adjacent to carbonyl (acetyl group, CH3-C=O)\n"
             "- delta 4.12 (2H, q, J = 7.1 Hz): Downfield CH2 ester oxygen neighbor (-O-CH2-CH3)\n"
             "FTIR Confirmation: Strong absorption band at 1735 cm^-1 (ester C=O stretch), 1240 cm^-1 (C-O stretch).\n"
             "Structure Assignment: Ethyl acetate (CH3-COO-CH2CH3).\n")
        ]
        return self.rng.choice(samples)

    def generate_corpus(self, num_samples: int = 100) -> List[Tuple[str, str]]:
        corpus = []
        generators = [
            (self.generate_organic_retrosynthesis, "chem_organic_retrosynthesis"),
            (self.generate_physical_thermodynamics, "chem_physical_thermodynamics"),
            (self.generate_inorganic_organometallics, "chem_inorganic_organometallics"),
            (self.generate_analytical_spectroscopy, "chem_analytical_spectroscopy")
        ]
        for _ in range(num_samples):
            fn, tag = self.rng.choice(generators)
            corpus.append((fn(), tag))
        return corpus


if __name__ == "__main__":
    syn = ChemistryMasterSynthesizer()
    c = syn.generate_corpus(4)
    print(f"[*] Chemistry Master Synthesizer: {len(CHEMISTRY_EXPERT_DOMAINS)} dedicated domains:")
    for d in CHEMISTRY_EXPERT_DOMAINS:
        print(f"  - {d}")
    print("\nSamples:")
    for txt, tag in c:
        print(f"[{tag}] -> {txt[:180]}...\n")
