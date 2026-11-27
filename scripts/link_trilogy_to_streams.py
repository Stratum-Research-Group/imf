#!/usr/bin/env python3
"""
scripts/link_trilogy_to_streams.py
Injects a consolidated Research Stream Navigation Appendix into each Volume
of the Sacred Sanctum trilogy, establishing bidirectional links between chapters
and the 113 Development Streams.
"""

import os
import glob

STREAM_PHASE_MAP = {
    "Volume I": ("Phase 1 & Phase 2", [
        "papers/phase_1_core_architecture/streams/STREAM_0001_0010_PAPER_1_LIE_ALGEBRAIC_MEMORY_SPLITTING_SYMMETRIC_A.md",
        "papers/phase_1_core_architecture/streams/STREAM_0011_0020_PAPER_11_UNIVERSAL_100_DOMAIN_POLYTOPE_MANIFOLDS_T.md",
        "papers/phase_2_formal_verification_and_math_physics/streams/STREAM_0081_0090_PAPER_81_AUTOMATED_EPISTEMIC_VERIFICATION_ACROSS_T.md"
    ]),
    "Volume II": ("Phase 3 & Phase 4", [
        "papers/phase_3_poincare_hyperbolic_kernels/streams/STREAM_0131_0140_PAPER_131_SYMPLECTIC_PHASE_SPACE_VOLUME_CONSERVATI.md",
        "papers/phase_3_poincare_hyperbolic_kernels/streams/STREAM_0151_0160_PAPER_151_FUSED_POINCAR_KEY_VALUE_CACHE_DECODING_A.md",
        "papers/phase_4_soliton_hierarchies/streams/STREAM_0201_0210_PAPER_201_FUSED_POINCAR_SAWADA_KOTERA_5TH_ORDER_SO.md"
    ]),
    "Volume III": ("Phase 5 & Phase 6", [
        "papers/phase_5_certified_scaling_lie_geometry_io/streams/STREAM_0286_0290_PAPER_286_POINCAR_DISCRETE_BOITI_LEON_PEMPINELLI_B.md",
        "papers/phase_6_blackwell_kernels_and_dma_engines/streams/STREAM_1291_1300_PAPER_1291_NINE_HUNDRED_SEVENTY_MILLION_STEPS_MOTIVIC_GOERSS.md",
        "papers/phase_6_blackwell_kernels_and_dma_engines/streams/STREAM_1281_1290_PAPER_1281_NINE_HUNDRED_SIXTY_MILLION_STEPS_THE_MOTIVIC_GROS.md"
    ])
}

def link_volumes():
    print("[*] Linking Trilogy Volumes to Consolidated Development Streams...")
    vols = [
        ("docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.md", "Volume I"),
        ("docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.md", "Volume II"),
        ("docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.md", "Volume III")
    ]

    for vpath, vtitle in vols:
        if not os.path.exists(vpath):
            continue
        with open(vpath, "r", encoding="utf-8") as f:
            content = f.read()

        phase_desc, sample_streams = STREAM_PHASE_MAP[vtitle]
        appendix = f"""
## Appendix S: Consolidated Development Stream Lineage ({phase_desc})
This volume's theoretical foundations and empirical systems are directly grounded in the IMF Development Stream Corpus:
- **Master Stream Catalog:** [`docs/MASTER_DEVELOPMENT_STREAMS_CATALOG.md`](../MASTER_DEVELOPMENT_STREAMS_CATALOG.md)
- **Primary Lineage Streams:**
"""
        for s in sample_streams:
            bn = os.path.basename(s).replace(".md", "")
            appendix += f"  - [`{bn}`](../../{s})\n"

        if "## Appendix S: Consolidated Development Stream Lineage" not in content:
            content += "\n" + appendix
            with open(vpath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  [+] Linked {vtitle} -> {vpath}")
        else:
            print(f"  [.] {vtitle} already linked.")

if __name__ == '__main__':
    link_volumes()
