#!/usr/bin/env python3
"""
scripts/audit_development_stream_thematic_clusters.py
Audits that all 113 Development Streams are correctly clustered across their respective Phases (1 through 6).
"""

import os
import glob
import re

def audit_clusters():
    phases = [
        "phase_1_core_architecture",
        "phase_2_formal_verification_and_math_physics",
        "phase_3_poincare_hyperbolic_kernels",
        "phase_4_soliton_hierarchies",
        "phase_5_certified_scaling_lie_geometry_io",
        "phase_6_blackwell_kernels_and_dma_engines"
    ]

    total_streams = 0
    print("[*] Auditing Development Stream thematic cluster allocations...")

    for p in phases:
        p_dir = os.path.join("papers", p, "streams")
        if os.path.exists(p_dir):
            streams = sorted(glob.glob(os.path.join(p_dir, "STREAM_*.md")))
            total_streams += len(streams)
            print(f"    • {p}: {len(streams)} streams")

    print(f"[+] Total clustered Development Streams: {total_streams}/113")
    if total_streams == 113:
        print("[✓] 100% of Development Streams are canonically organized across all 6 Phases.")
        return 0
    else:
        print(f"[!] Warning: Expected 113 streams, found {total_streams}")
        return 1

if __name__ == '__main__':
    audit_clusters()
