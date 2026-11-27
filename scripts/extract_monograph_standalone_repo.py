#!/usr/bin/env python3
"""
scripts/extract_monograph_standalone_repo.py
Extracts the complete Sacred Sanctum Monograph trilogy, visualizers,
Lean 4 proofs, and compilation scripts into an independent git repository bundle in dist/.
"""

import os
import shutil
import subprocess

def extract_standalone_repo():
    target_dir = "dist/sacred_sanctum_standalone_repo"
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    print(f"[*] Extracting standalone monograph repository into {target_dir}...")

    # Copy files
    shutil.copytree("docs/thesis", os.path.join(target_dir, "docs/thesis"))
    shutil.copytree("docs/visualizers", os.path.join(target_dir, "docs/visualizers"))
    shutil.copytree("docs/lean4_docs", os.path.join(target_dir, "docs/lean4_docs"))
    shutil.copytree("notebooks", os.path.join(target_dir, "notebooks"))
    shutil.copytree("lean_pilot", os.path.join(target_dir, "lean_pilot"))

    # Copy root files and scripts
    os.makedirs(os.path.join(target_dir, "scripts"), exist_ok=True)
    shutil.copy("scripts/generate_thesis_pdfs.py", os.path.join(target_dir, "scripts/generate_thesis_pdfs.py"))
    shutil.copy("scripts/compile_latex_monograph.py", os.path.join(target_dir, "scripts/compile_latex_monograph.py"))
    shutil.copy("scripts/build_epub_editions.py", os.path.join(target_dir, "scripts/build_epub_editions.py"))

    # Initialize git repo in target
    subprocess.run(["git", "init"], cwd=target_dir, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Stratum Research Group"], cwd=target_dir, check=True)
    subprocess.run(["git", "config", "user.email", "research@stratum.group"], cwd=target_dir, check=True)
    subprocess.run(["git", "add", "."], cwd=target_dir, check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial release of The Sacred Sanctum standalone repository"], cwd=target_dir, check=True, stdout=subprocess.DEVNULL)

    print(f"[+] Successfully extracted pristine standalone git repository at: {target_dir}")

if __name__ == '__main__':
    extract_standalone_repo()
