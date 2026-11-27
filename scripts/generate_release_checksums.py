#!/usr/bin/env python3
"""
scripts/generate_release_checksums.py
Generates cryptographic SHA-256 and SHA-512 checksum manifests for all
compiled PDFs, EPUBs, LaTeX zip archives, and model checkpoints.
"""

import os
import hashlib
import glob

def compute_hashes(filepath):
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
            sha512.update(chunk)
    return sha256.hexdigest(), sha512.hexdigest()

def main():
    files = sorted(glob.glob('docs/thesis/*.pdf') + 
                   glob.glob('docs/thesis/compiled/*.epub') + 
                   glob.glob('docs/thesis/*.zip') + 
                   glob.glob('checkpoints/sovereign_7b_release/*'))

    out_lines_sha512 = ["# The Sacred Sanctum Cryptographic SHA-512 Checksum Manifest",
                        "# Generated automatically by Stratum Research Group\n"]
    out_lines_sha256 = ["# The Sacred Sanctum Cryptographic SHA-256 Checksum Manifest\n"]

    print(f"Generating checksums for {len(files)} release artifacts...")
    for f in files:
        if os.path.isfile(f):
            h256, h512 = compute_hashes(f)
            rel = os.path.relpath(f, '.')
            out_lines_sha512.append(f"{h512}  {rel}")
            out_lines_sha256.append(f"{h256}  {rel}")
            print(f"[+] {rel}: SHA-256 = {h256[:16]}... | SHA-512 = {h512[:16]}...")

    with open('docs/thesis/CHECKSUMS.sha512', 'w') as f:
        f.write("\n".join(out_lines_sha512) + "\n")
    with open('docs/thesis/CHECKSUMS.sha256', 'w') as f:
        f.write("\n".join(out_lines_sha256) + "\n")

    print("[+] Wrote docs/thesis/CHECKSUMS.sha512 and CHECKSUMS.sha256 successfully.")

if __name__ == '__main__':
    main()
