#!/usr/bin/env python3
"""
Inspect whether C++ / CUDA header includes (<vector>, <cuda_runtime.h>) or math (<u, v>)
are leaking into raw Markdown prose outside of code blocks (``` ... ``` or ` ... `).
"""
import glob
import os
import re

files = sorted(glob.glob("docs/thesis/volume_*/chapter_*.md"))

for fpath in files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Remove all code blocks
    no_code_blocks = re.sub(r'```[\s\S]*?```', '', content)
    # Remove inline code
    no_inline_code = re.sub(r'`[^`]*`', '', no_code_blocks)
    
    # Check for unescaped HTML-like patterns
    matches = re.findall(r'<(?!\/?(?:div|img|span|br|b|i|table|tr|th|td|sub|sup|details|summary|h[1-6]|p|pre|code)\b)[a-zA-Z0-9_\s,\.\+\-\*\/]+>', no_inline_code)
    if matches:
        print(f"[!] Leak outside code blocks in {fname}: {matches}")
