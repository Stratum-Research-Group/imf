#!/usr/bin/env python3
"""
scripts/generate_audio_monograph.py
Synthesizes spoken narration of master chapter abstracts and introductions
into clear audio format using gTTS / local audio pipeline.
"""

import os
import re
from gtts import gTTS

def clean_text_for_speech(text):
    # Remove markdown headers, code blocks, LaTeX math
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'\$[^\$]+\$', ' [formula] ', text)
    text = re.sub(r'[#\*_`]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def synthesize_chapter_brief(chapter_path, out_mp3):
    with open(chapter_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract Title and Abstract
    title_match = re.search(r'^#\s+(.+)$', content, re.M)
    title = title_match.group(1) if title_match else "Chapter Brief"

    abstract_match = re.search(r'## Abstract\s+([\s\S]*?)(?=##|\Z)', content)
    abstract = abstract_match.group(1) if abstract_match else ""

    speech_text = f"{title}. Abstract. {clean_text_for_speech(abstract)[:800]}"
    print(f"[*] Synthesizing narration for: {title}...")

    tts = gTTS(text=speech_text, lang='en', slow=False)
    os.makedirs(os.path.dirname(out_mp3), exist_ok=True)
    tts.save(out_mp3)
    print(f"[+] Generated audio: {out_mp3} ({os.path.getsize(out_mp3) / 1024:.1f} KB)")

def main():
    targets = [
        ("docs/thesis/volume_1_dimensional_spaces/chapter_01_discrete_differential_geometry_and_exterior_calculus.md",
         "docs/thesis/audio/vol1_ch1_narration.mp3"),
        ("docs/thesis/volume_2_higher_dimensional_spaces/chapter_03_the_gosset_e8_polytope_and_optimal_8d_sphere_packing.md",
         "docs/thesis/audio/vol2_ch3_narration.mp3"),
        ("docs/thesis/volume_3_transfinite_ultra_dimensional_spaces/chapter_04_the_chromatic_tower_and_stable_homotopy_spheres.md",
         "docs/thesis/audio/vol3_ch4_narration.mp3")
    ]

    for ch_path, mp3_path in targets:
        if os.path.exists(ch_path):
            synthesize_chapter_brief(ch_path, mp3_path)

if __name__ == '__main__':
    main()
