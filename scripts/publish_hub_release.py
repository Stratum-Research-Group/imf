#!/usr/bin/env python3
"""
scripts/publish_hub_release.py

Packaging and manifest staging utility for publishing IMF 1.14B foundation model weights,
Lean 4 formal verification proofs, and the 36-paper research compendium to Hugging Face
Hub and public research archives.
"""

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def prepare_release_manifest():
    print("=" * 65)
    print("  IMF 1.14B Open-Weights & Research Release Staging")
    print("=" * 65)

    release_assets = [
        ROOT / "checkpoints" / "imf_foundation_1b.imf",
        ROOT / "checkpoints" / "imf_drafter_fluency_4k.imf",
        ROOT / "dist" / "imf_preprint.pdf",
        ROOT / "dist" / "imf-1.0.0-py3-none-any.whl",
        ROOT / "MODEL_CARD.md"
    ]

    manifest = {
        "release": "v1.0.0",
        "organization": "Stratum-Research-Group",
        "model_name": "imf-foundation-1b",
        "license": "Apache-2.0",
        "assets": []
    }

    for p in release_assets:
        if p.exists():
            size_mb = p.stat().st_size / (1024 * 1024)
            sha = compute_sha256(p)
            manifest["assets"].append({
                "file": p.name,
                "size_mb": round(size_mb, 2),
                "sha256": sha
            })
            print(f"  [✓] Staged: {p.name:<32} ({size_mb:>8.2f} MB) | SHA: {sha[:12]}...")
        else:
            print(f"  [!] Missing asset: {p.name}")

    out_path = ROOT / "dist" / "hub_release_manifest.json"
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[✓] Staged Hub release manifest written to: {out_path}")

if __name__ == "__main__":
    prepare_release_manifest()
