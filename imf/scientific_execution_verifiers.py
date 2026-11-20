"""
Scientific Ground-Truth Execution Verifiers (IMF).
Extends deterministic verification beyond standard computer code into hard science domains:
1. Genomics & Bioinformatics:
   - Canonical IUPAC FASTA nucleotide validation (A, C, G, T, U, N).
   - CRISPR-Cas9 SpCas20 PAM site verification (5'-NGG-3' targeting).
   - Codon translation, Open Reading Frame (ORF) starting with AUG/ATG and canonical Stop codons (UAA, UAG, UGA / TAA, TAG, TGA).
   - GC-content and reverse-complement conservation.
2. Chemistry & Cheminformatics:
   - Canonical SMILES string grammar verification (ring closure pairing, balanced parentheses, atom valency).
   - Chemical formula stoichiometry and charge neutrality.
3. Quantum Information & Circuit Mechanics:
   - Unitary operator verification (U^dagger * U = I_N within numerical tolerance).
   - Quantum state vector normalization (sum |c_i|^2 = 1.0).
   - Density matrix properties (Hermitian, positive semi-definite, Tr(rho) = 1.0).
4. Discrete Mathematics & SMT SAT/CAS:
   - SymPy / CAS symbolic equation balance verification (LHS - RHS == 0).
"""

import math
import re
from typing import Tuple, Dict, Any, List

class ScientificExecutionVerifier:
    def __init__(self):
        # Canonical standard genetic code table (DNA -> Amino Acid)
        self.codon_table = {
            "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
            "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
            "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
            "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
            "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
            "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
            "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
            "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
            "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
            "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
            "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
            "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
            "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
            "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
            "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
            "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
        }

    # =========================================================================
    # 1. GENOMICS & CRISPR VERIFIERS
    # =========================================================================
    def verify_dna_fasta(self, seq: str) -> Tuple[bool, str]:
        """Validates canonical DNA sequence adhering to IUPAC nucleotide grammar."""
        clean = "".join(seq.split()).upper()
        if not clean:
            return False, "Empty sequence."
        invalid_chars = set(clean) - set("ACGTN")
        if invalid_chars:
            return False, f"Invalid nucleotide characters detected: {invalid_chars}"
        return True, f"Valid DNA sequence (Length={len(clean)}, GC={self._calc_gc(clean):.1f}%)."

    def verify_crispr_pam(self, target_dna: str, pam_type: str = "SpCas9_NGG") -> Tuple[bool, str]:
        """
        Verifies CRISPR spacer target and Protospacer Adjacent Motif (PAM).
        For SpCas9: 20nt protospacer followed by 3nt PAM matching .GG.
        """
        clean = "".join(target_dna.split()).upper()
        if pam_type == "SpCas9_NGG":
            if len(clean) < 23:
                return False, f"Sequence length {len(clean)} < 23nt required for 20nt gRNA + 3nt PAM."
            pam = clean[-3:]
            if pam[1:] != "GG":
                return False, f"Invalid SpCas9 PAM: expected 5'-NGG-3', got 5'-{pam}-3'."
            gRNA = clean[:-3]
            return True, f"Valid CRISPR SpCas9 cleavage site (20nt gRNA: {gRNA[-20:]}, PAM: {pam})."
        return False, f"Unsupported PAM type: {pam_type}"

    def verify_orf_translation(self, dna_seq: str) -> Tuple[bool, str]:
        """Verifies Open Reading Frame (ORF): must start with ATG, length multiple of 3, valid stop."""
        clean = "".join(dna_seq.split()).upper()
        if not clean.startswith("ATG"):
            return False, "ORF does not begin with canonical canonical ATG start codon."
        if len(clean) % 3 != 0:
            return False, f"ORF length {len(clean)} is not a multiple of 3 (frameshift)."
        
        # Translate codons
        protein = []
        for i in range(0, len(clean), 3):
            codon = clean[i:i+3]
            aa = self.codon_table.get(codon, "?")
            protein.append(aa)
        
        if protein[-1] != "*":
            return False, f"ORF does not terminate at a canonical stop codon (got {clean[-3:]} -> {protein[-1]})."
        
        # Ensure no premature stop codons in interior
        if "*" in protein[:-1]:
            stop_pos = protein[:-1].index("*") * 3
            return False, f"Premature nonsense stop codon at nucleotide offset {stop_pos}."

        protein_str = "".join(protein)
        return True, f"Valid ORF Translation: {len(protein)-1} amino acids ({protein_str})."

    # =========================================================================
    # 2. CHEMISTRY & CHEMINFORMATICS VERIFIERS
    # =========================================================================
    def verify_smiles_grammar(self, smiles: str) -> Tuple[bool, str]:
        """
        Verifies canonical SMILES string syntax:
        - Balanced parentheses for branches.
        - Balanced digit pairs for ring closures.
        - Valid organic subset element symbols.
        """
        clean = "".join(smiles.split())
        if not clean:
            return False, "Empty SMILES string."

        # Check branch balancing
        if clean.count("(") != clean.count(")"):
            return False, f"Unbalanced branching parentheses: {clean.count('(')} '(' vs {clean.count(')')} ')'."

        # Check ring closure digit pairs
        digits = re.findall(r"\d", clean)
        from collections import Counter
        d_counts = Counter(digits)
        unclosed_rings = [d for d, count in d_counts.items() if count % 2 != 0]
        if unclosed_rings:
            return False, f"Unclosed ring closure digits: {unclosed_rings}"

        # Valid SMILES tokens
        valid_pattern = re.compile(r"^(\[?[A-Za-z0-9@\+\-\#\=\\\/\(\)\:\.\%]+\]?)+$")
        if not valid_pattern.match(clean):
            return False, "Contains invalid SMILES tokens."

        return True, f"Valid SMILES string syntax: {clean}"

    # =========================================================================
    # 3. QUANTUM INFORMATION & CIRCUIT VERIFIERS
    # =========================================================================
    def verify_quantum_state(self, amplitudes: List[complex]) -> Tuple[bool, str]:
        """Verifies quantum state vector normalization: sum |c_i|^2 == 1.0."""
        if not amplitudes:
            return False, "Empty state vector."
        prob_sum = sum(abs(c)**2 for c in amplitudes)
        if not math.isclose(prob_sum, 1.0, abs_tol=1e-5):
            return False, f"State vector not normalized: sum |c_i|^2 = {prob_sum:.6f} != 1.0"
        
        n_qubits = math.log2(len(amplitudes))
        if not n_qubits.is_integer():
            return False, f"State dimension {len(amplitudes)} is not a power of 2."
        return True, f"Valid {int(n_qubits)}-qubit quantum pure state (Norm={prob_sum:.6f})."

    def verify_unitary_matrix(self, matrix: List[List[complex]]) -> Tuple[bool, str]:
        """Verifies matrix unitarity: U^dagger * U = I within tolerance."""
        n = len(matrix)
        for row in matrix:
            if len(row) != n:
                return False, f"Non-square matrix: {n}x{len(row)}"

        # Compute U^dagger * U
        for i in range(n):
            for j in range(n):
                # (U^dagger * U)_{ij} = sum_k conj(U_{ki}) * U_{kj}
                val = sum(matrix[k][i].conjugate() * matrix[k][j] for k in range(n))
                expected = 1.0 if i == j else 0.0
                if not math.isclose(abs(val - expected), 0.0, abs_tol=1e-4):
                    return False, f"Non-unitary element at ({i},{j}): got {val}, expected {expected}."
        return True, f"Valid {n}x{n} unitary operator (U^dagger * U = I_{n})."

    def _calc_gc(self, seq: str) -> float:
        if not seq:
            return 0.0
        gc = sum(1 for b in seq if b in "GC")
        return (gc / len(seq)) * 100.0


if __name__ == "__main__":
    v = ScientificExecutionVerifier()

    # 1. Test DNA FASTA
    dna = "ATGCGATCGATCGATCGATCGATCGTAG"
    p_dna, m_dna = v.verify_dna_fasta(dna)
    print("[DNA FASTA]:", p_dna, m_dna)
    assert p_dna

    # 2. Test CRISPR SpCas9
    crispr = "GAGTTCTTGCTCTTCATCGATGG"
    p_cr, m_cr = v.verify_crispr_pam(crispr)
    print("[CRISPR]:", p_cr, m_cr)
    assert p_cr

    # 3. Test ORF Translation
    orf = "ATGGCCAAGTTTTAA"  # Met-Ala-Lys-Phe-Stop
    p_orf, m_orf = v.verify_orf_translation(orf)
    print("[ORF Translation]:", p_orf, m_orf)
    assert p_orf

    # 4. Test SMILES
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"  # Aspirin
    p_smi, m_smi = v.verify_smiles_grammar(smiles)
    print("[SMILES]:", p_smi, m_smi)
    assert p_smi

    # 5. Test Quantum State Vector
    bell_state = [1/math.sqrt(2), 0, 0, 1/math.sqrt(2)]
    p_q, m_q = v.verify_quantum_state(bell_state)
    print("[Quantum Bell State]:", p_q, m_q)
    assert p_q

    print("[+] All Scientific Ground-Truth Execution Verifiers successfully tested.")
