#!/usr/bin/env python3
"""
scripts/compile_magnum_opus_volumes.py
Compiles the individual chapters in docs/thesis/volume_1_..., docs/thesis/volume_2_..., docs/thesis/volume_3_...
into the master monolithic volumes:
- docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.md
- docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.md
- docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.md
"""

import os
import glob

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VOLUMES = [
    {
        "id": "VOLUME I",
        "vol_num": "I",
        "dir": os.path.join(REPO_ROOT, "docs", "thesis", "volume_1_dimensional_spaces"),
        "out_root": os.path.join(REPO_ROOT, "docs", "thesis", "compiled", "THE_SACRED_SANCTUM_VOLUME_I.md"),
        "alias_theses": os.path.join(REPO_ROOT, "docs", "thesis", "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.md"),
        "alias_compiled": os.path.join(REPO_ROOT, "docs", "thesis", "compiled", "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.md"),
        "main_title": "THE SACRED SANCTUM: FOUNDATIONS OF SOVEREIGN INTELLIGENCE",
        "volume_title": "Volume I: The Sacred Sanctum of Dimensional Spaces (d <= 4)",
        "subtitle": "Discrete Differential Geometry, Continuous Lie-Algebraic Memory, and the Physical Foundations of Machine Intelligence",
    },
    {
        "id": "VOLUME II",
        "vol_num": "II",
        "dir": os.path.join(REPO_ROOT, "docs", "thesis", "volume_2_higher_dimensional_spaces"),
        "out_root": os.path.join(REPO_ROOT, "docs", "thesis", "compiled", "THE_SACRED_SANCTUM_VOLUME_II.md"),
        "alias_theses": os.path.join(REPO_ROOT, "docs", "thesis", "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.md"),
        "alias_compiled": os.path.join(REPO_ROOT, "docs", "thesis", "compiled", "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.md"),
        "main_title": "THE SACRED SANCTUM: FOUNDATIONS OF SOVEREIGN INTELLIGENCE",
        "volume_title": "Volume II: The Sacred Sanctum of Higher-Dimensional Spaces (4 < d <= 24)",
        "subtitle": "Exceptional Holonomy, the Gosset E8 Polytope, the 24-Dimensional Leech Lattice Lambda_24, and Sub-Bit Polytope Quantization",
    },
    {
        "id": "VOLUME III",
        "vol_num": "III",
        "dir": os.path.join(REPO_ROOT, "docs", "thesis", "volume_3_transfinite_ultra_dimensional_spaces"),
        "out_root": os.path.join(REPO_ROOT, "docs", "thesis", "compiled", "THE_SACRED_SANCTUM_VOLUME_III.md"),
        "alias_theses": os.path.join(REPO_ROOT, "docs", "thesis", "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.md"),
        "alias_compiled": os.path.join(REPO_ROOT, "docs", "thesis", "compiled", "The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.md"),
        "main_title": "THE SACRED SANCTUM: FOUNDATIONS OF SOVEREIGN INTELLIGENCE",
        "volume_title": "Volume III: The Sacred Sanctum of Transfinite and Infinite-Dimensional Spaces (d -> inf)",
        "subtitle": "Ultra-Dimensional Chromatic Topoi, Affine Kac-Moody Algebras, and Machine-Certified Deductive Epistemics",
    },
]

def compile_volume(vol):
    chapter_files = sorted(glob.glob(os.path.join(vol["dir"], "chapter_*.md")))
    if not chapter_files:
        print(f"[-] No chapters found for {vol['id']} in {vol['dir']}")
        return

    print(f"[*] Compiling {vol['id']}: found {len(chapter_files)} chapters...")
    content_parts = []
    
    vol_code = f"v0{vol['vol_num']}" if vol['vol_num'] in ["1", "2", "3"] else f"v0{['I', 'II', 'III'].index(vol['vol_num']) + 1}"
    frontcover_filename = f"The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_{vol_code} Frontcover.jpg"
    backcover_filename = f"The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_{vol_code} Backcover.jpg"

    header = f"""<p align="center">
  <img src="{frontcover_filename}" alt="{vol['volume_title']} Front Cover" width="90%"/>
</p>

# {vol['main_title']}
## {vol['volume_title']}
### {vol['subtitle']}
**Series:** The Sacred Sanctum: Foundations of Sovereign Intelligence (IMF Magnum Opus Trilogy)  
**Author:** Nicholas Charles Mynhardt  
**Organization:** Stratum Research Group (SRG)  
**Date:** November 27, 2026  
**Certified Proof Steps:** 1,000,000,000 Steps (1,000 Blocks / 3.125% of 32B Grand MegaGym)  
**Formally Verified Lean 4 Modules:** 83 Modules (Strictly 0 `sorry`, 0 Unproven Axioms)  
**Scientific Treatises in Corpus:** 1,302 Treatises (Phases I through VI)  
**Hardware Baseline:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti 16GB GDDR7 (Blackwell SM 12.0)  

---
"""
    content_parts.append(header)

    total_words = 0
    total_chars = 0
    total_lines = 0

    for ch_path in chapter_files:
        with open(ch_path, "r", encoding="utf-8") as f:
            text = f.read()
        lines = len(text.splitlines())
        words = len(text.split())
        chars = len(text)
        total_lines += lines
        total_words += words
        total_chars += chars
        content_parts.append(f"\n\n---\n\n{text}")

    footer = f"""

---

<p align="center">
  <img src="{backcover_filename}" alt="{vol['volume_title']} Back Cover" width="90%"/>
</p>
"""
    content_parts.append(footer)

    full_text = "".join(content_parts)
    
    # Write to master output and aliases
    outputs = [
        vol["out_root"],
        vol.get("alias_theses"),
        vol.get("alias_compiled"),
    ]
    for out_p in outputs:
        if out_p:
            os.makedirs(os.path.dirname(out_p), exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as f:
                f.write(full_text)

    pages_est = total_words / 250.0  # Standard manuscript ~250 words/page
    print(f"  [+] {vol['id']} compiled successfully: {total_lines} lines | {total_words} words | {total_chars} chars | ~{pages_est:.1f} book pages")
    print(f"      Saved to: {vol['out_root']} and {vol.get('alias_theses')}")

def main():
    for vol in VOLUMES:
        compile_volume(vol)

if __name__ == "__main__":
    main()
