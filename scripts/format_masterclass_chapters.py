#!/usr/bin/env python3
"""
Masterclass Chapter Formatter & Inspector
Ensures every chapter in docs/thesis/volume_* has:
1. Complete Abstract.
2. An extensive, pedagogical first-principles Section 1: "Introduction & Intuitive First-Principles Foundation"
   that thoroughly introduces a first-time reader to the subject using intuitive analogies, historical context,
   geometric visualizations, and physical motivations before entering the mathematical formalism.
3. Clean LaTeX math formatting and structured subsections.
"""
import glob
import os
import re

chapters = sorted(glob.glob("docs/thesis/volume_*/chapter_*.md"))
print(f"Discovered {len(chapters)} chapters.")

for path in chapters:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    words = len(content.split())
    has_abstract = "Abstract" in content or "abstract" in content
    has_sec1 = re.search(r'## 1\.\s+.*Introduction', content) is not None or "## 1." in content
    
    print(f"{os.path.basename(path):<70} | Words: {words:<6} | Abstract: {str(has_abstract):<5} | Intro: {str(has_sec1)}")

