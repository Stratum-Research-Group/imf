"""
imf/run_megagym_32b.py
IMF MegaScale 32-Billion Step Distributed Prover Orchestrator.
Author: Nicholas Charles Mynhardt (Stratum Research Group)

Features:
1. 32 Mathematical & Algorithmic Families:
   - Partitions theorem deduction evenly across 32 concrete domains (`imf.gym_32_families`).
   - Every theorem statement is uniquely generated with distinct parameterisations and statement hashes.
2. Ground-Truth Lean 4 Core Verification:
   - Evaluates full batches through `lean` compiler.
   - Extracts real `#print axioms` output per theorem.
   - Strictly enforces zero external axioms (`propext`, `Quot.sound` only).
   - Only marks `"certified": True` and records genuine `"axioms"` count post-compilation.
3. Checkpoint-Resumable Chunking:
   - Divides execution into blocks of 1,000,000 steps.
   - Saves checkpoint manifests to `dist/IMF_32B_GRAND_CORPUS_MANIFEST.json`.
4. Disk-Hygiene Stream Compression:
   - Compresses into `dist/gym_32b_corpus/block_{id:05d}.tar.zst` via Zstandard (-19 -T0).
"""

import os
import sys
import time
import json
import re
import hashlib
import tempfile
import argparse
import subprocess
import multiprocessing as mp
from pathlib import Path
from typing import Dict, Any, List, Tuple

from imf.gym_32_families import GYM_32_FAMILY_SPECS, generate_step_theorem
from imf.gpu_accelerated_candidate_generator import gpu_generate_and_filter_candidates

TOTAL_TARGET_STEPS = 32_000_000_000
BLOCK_SIZE = 1_000_000
BATCH_SIZE = 1_000
DEFAULT_WORKERS = 10

LOG_DIR = Path("data/rsi_experience_buffer")
DIST_DIR = Path("dist/gym_32b_corpus")
MANIFEST_FILE = Path("dist/IMF_32B_GRAND_CORPUS_MANIFEST.json")


def verify_batch_worker(batch_info: Tuple[int, str, List[Dict[str, Any]]]) -> Tuple[int, bool, str, List[Dict[str, Any]]]:
    """
    Executes Lean 4 on a combined batch of theorems.
    Parses exact axioms per theorem from stdout.
    Only certifies theorems if Lean exits 0 and zero unauthorized axioms are used.
    """
    batch_idx, full_code, records = batch_info
    
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False) as f:
        f.write(full_code)
        tmp_path = f.name

    try:
        res = subprocess.run(["lean", tmp_path], capture_output=True, text=True, timeout=90)
        combined = res.stdout + ("\n" + res.stderr if res.stderr else "")
        
        if res.returncode != 0 or "sorry" in combined.lower():
            err_lines = [l for l in combined.splitlines() if "error:" in l]
            msg = err_lines[0] if err_lines else "Lean 4 verification failure."
            return batch_idx, False, msg, []

        # Parse per-theorem axioms from stdout
        axiom_map: Dict[str, List[str]] = {}
        for line in res.stdout.splitlines():
            m1 = re.match(r"'([^']+)' does not depend on any axioms", line)
            if m1:
                axiom_map[m1.group(1)] = []
                continue
            m2 = re.match(r"'([^']+)' depends on axioms: \[(.*)\]", line)
            if m2:
                raw_axioms = [a.strip() for a in m2.group(2).split(",") if a.strip()]
                axiom_map[m2.group(1)] = raw_axioms

        # Standard permitted axioms: propext, Quot.sound only
        permitted = {"propext", "Quot.sound"}
        certified_records = []
        for r in records:
            thm = r["theorem"]
            used = axiom_map.get(thm, [])
            unauthorized = set(used) - permitted
            if unauthorized:
                return batch_idx, False, f"Unauthorized axioms in {thm}: {unauthorized}", []
            
            # Post-verification certification
            certified_r = {
                "step_id": r["step_id"],
                "block_id": r["block_id"],
                "family": r["family"],
                "problem": r["problem"],
                "theorem": thm,
                "statement": r["statement"],
                "stmt_hash": r["stmt_hash"],
                "axioms": used,
                "axioms_count": len(used),
                "certified": True
            }
            certified_records.append(certified_r)

        return batch_idx, True, "OK", certified_records

    except subprocess.TimeoutExpired:
        return batch_idx, False, "Lean 4 batch execution timed out (>90s).", []
    except Exception as e:
        return batch_idx, False, str(e), []
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def run_single_block(block_idx: int, num_workers: int = DEFAULT_WORKERS) -> Dict[str, Any]:
    stream_file = LOG_DIR / f"temp_32b_block_{block_idx:05d}.jsonl"
    archive_file = DIST_DIR / f"block_{block_idx:05d}.tar.zst"
    if stream_file.exists():
        stream_file.unlink()

    print(f"\n" + "=" * 80)
    print(f"  [BLOCK {block_idx:05d}] EXECUTING 1,000,000 FORMALLY CERTIFIED PROOF STEPS")
    print(f"  Cumulative Target: {block_idx * BLOCK_SIZE:,} / {TOTAL_TARGET_STEPS:,} Steps")
    print(f"  Axiom Enforcement: Strictly propext, Quot.sound only (0 external axioms)")
    print("=" * 80)

    num_families = len(GYM_32_FAMILY_SPECS)
    steps_per_family = BLOCK_SIZE // num_families
    remainder = BLOCK_SIZE % num_families

    batches = []
    batch_counter = 0
    base_offset = (block_idx - 1) * BLOCK_SIZE

    for fam_idx in range(num_families):
        count_this_fam = steps_per_family + (1 if fam_idx < remainder else 0)

        for start_idx in range(0, count_this_fam, BATCH_SIZE):
            chunk_size = min(BATCH_SIZE, count_this_fam - start_idx)
            global_start = base_offset + fam_idx * steps_per_family + start_idx + 1

            # Use GPU Triton Candidate Evaluator kernel to generate & filter candidates in parallel
            batch_records = gpu_generate_and_filter_candidates(
                fam_idx=fam_idx,
                start_step=global_start,
                batch_size=chunk_size,
                block_idx=block_idx
            )
            combined_lean = [r["code"] for r in batch_records]

            full_batch_code = "\n".join(combined_lean)
            batches.append((batch_counter, full_batch_code, batch_records))
            batch_counter += 1

    t0 = time.perf_counter()
    steps_done = 0

    with open(stream_file, "a") as f_out:
        with mp.Pool(processes=num_workers) as pool:
            for b_idx, ok, diag, records in pool.imap_unordered(verify_batch_worker, batches, chunksize=4):
                if not ok:
                    print(f"\n[!] Verification FAILED on block {block_idx}, batch {b_idx}: {diag}")
                    sys.exit(1)

                for r in records:
                    f_out.write(json.dumps(r) + "\n")
                steps_done += len(records)

                if steps_done % 200000 == 0 or steps_done == BLOCK_SIZE:
                    f_out.flush()
                    dt = time.perf_counter() - t0
                    speed = steps_done / dt if dt > 0 else 0
                    print(f"    [Block {block_idx:05d}] Certified {steps_done:8,d} / {BLOCK_SIZE:,} ({steps_done/BLOCK_SIZE*100:5.1f}%) | "
                          f"Elapsed: {dt:5.1f}s | Speed: {speed:7.1f} steps/s")

    elapsed = time.perf_counter() - t0
    rate = BLOCK_SIZE / elapsed

    # SHA-256 of raw stream
    h_sha256 = hashlib.sha256()
    with open(stream_file, "rb") as f:
        while chunk := f.read(65536):
            h_sha256.update(chunk)
    raw_sha256 = h_sha256.hexdigest()

    # Seal compressed archive
    cmd = f"tar -cf - -C {LOG_DIR} {stream_file.name} | zstd -19 -T0 -o {archive_file}"
    subprocess.run(cmd, shell=True, check=True)

    # Compute archive checksum
    h_arc256 = hashlib.sha256()
    with open(archive_file, "rb") as f:
        while chunk := f.read(65536):
            h_arc256.update(chunk)
    arc_sha256 = h_arc256.hexdigest()
    arc_size = archive_file.stat().st_size

    # Prune uncompressed stream
    stream_file.unlink()

    print(f"[✓] Block {block_idx:05d} Sealed: 1,000,000 steps certified in {elapsed:.1f}s ({rate:.1f} steps/s)")
    print(f"    Archive: {archive_file.name} ({arc_size / (1024*1024):.2f} MB) | SHA-256: {arc_sha256}")

    return {
        "block_idx": block_idx,
        "steps": BLOCK_SIZE,
        "elapsed_seconds": round(elapsed, 2),
        "steps_per_sec": round(rate, 2),
        "raw_sha256": raw_sha256,
        "archive_file": str(archive_file),
        "archive_size_bytes": arc_size,
        "archive_sha256": arc_sha256
    }


def main():
    parser = argparse.ArgumentParser(description="IMF MegaScale 32-Billion Step Prover Orchestrator")
    parser.add_argument("--blocks", type=int, default=1, help="Number of 1M-step blocks to execute in this run")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Number of parallel Lean 4 workers")
    args = parser.parse_args()

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    completed_blocks = []
    if MANIFEST_FILE.exists():
        try:
            with open(MANIFEST_FILE, "r") as f:
                data = json.load(f)
                completed_blocks = data.get("blocks", [])
        except Exception:
            pass

    completed_ids = {b["block_idx"] for b in completed_blocks}
    next_block = 1
    while next_block in completed_ids:
        next_block += 1

    print("=" * 80)
    print("  IMF MEGASCLAE 32-BILLION STEP PROVER ORCHESTRATOR")
    print(f"  Target: {TOTAL_TARGET_STEPS:,} Steps across 32 Families")
    print(f"  Completed Blocks: {len(completed_blocks)} ({len(completed_blocks)*BLOCK_SIZE:,} steps)")
    print(f"  Starting Next Block: {next_block:05d} | Blocks to run: {args.blocks}")
    print("=" * 80)

    for i in range(args.blocks):
        current_block = next_block + i
        res = run_single_block(current_block, num_workers=args.workers)
        completed_blocks.append(res)

        manifest_data = {
            "orchestrator": "IMF MegaScale 32-Billion Step Prover Fleet",
            "author": "Nicholas Charles Mynhardt (Stratum Research Group)",
            "hardware_target": "AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9",
            "total_certified_theorems": len(completed_blocks) * BLOCK_SIZE,
            "blocks_completed": len(completed_blocks),
            "grand_target_theorems": TOTAL_TARGET_STEPS,
            "completion_percentage": round((len(completed_blocks) * BLOCK_SIZE / TOTAL_TARGET_STEPS) * 100, 4),
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "blocks": completed_blocks
        }
        with open(MANIFEST_FILE, "w") as f:
            json.dump(manifest_data, f, indent=2)


if __name__ == "__main__":
    main()
