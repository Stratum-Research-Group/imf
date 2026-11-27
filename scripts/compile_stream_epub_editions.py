#!/usr/bin/env python3
"""
scripts/compile_stream_epub_editions.py
Generates three omnibus EPUB3 editions for the 113 Development Streams:
1. Phase_I_II_Streams.epub
2. Phase_III_IV_Streams.epub
3. Phase_V_VI_Streams.epub
Uses pandoc or python-based packaging.
"""

import os
import glob
import subprocess

def compile_epubs():
    out_dir = "dist/stream_ebooks"
    os.makedirs(out_dir, exist_ok=True)
    print(f"[*] Compiling Omnibus EPUB3 Editions in {out_dir}...")

    groups = [
        ("Phase_I_II_Streams.epub", "IMF Omnibus Edition: Phases I & II", [
            p for p in glob.glob("papers/phase_[12]_*/streams/STREAM_*.md")
        ]),
        ("Phase_III_IV_Streams.epub", "IMF Omnibus Edition: Phases III & IV", [
            p for p in glob.glob("papers/phase_[34]_*/streams/STREAM_*.md")
        ]),
        ("Phase_V_VI_Streams.epub", "IMF Omnibus Edition: Phases V & VI", [
            p for p in glob.glob("papers/phase_[56]_*/streams/STREAM_*.md")
        ])
    ]

    for ep_name, ep_title, files in groups:
        ep_path = os.path.join(out_dir, ep_name)
        sorted_files = sorted(files)
        if not sorted_files:
            continue

        print(f"  [*] Building {ep_name} from {len(sorted_files)} streams...")
        # Check pandoc availability
        has_pandoc = subprocess.run(["which", "pandoc"], capture_output=True).returncode == 0
        if has_pandoc:
            cmd = [
                "pandoc", "-o", ep_path,
                f"--metadata=title:{ep_title}",
                "--metadata=author:Nicholas Charles Mynhardt (Stratum Research Group)"
            ] + sorted_files
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                print(f"  [+] Generated: {ep_path} ({os.path.getsize(ep_path) / 1024:.1f} KB)")
            else:
                print(f"  [!] Pandoc warning: {res.stderr[:100]}")
        else:
            # Generate a structured metadata container
            with open(ep_path + ".txt", "w", encoding="utf-8") as out_txt:
                out_txt.write(f"# {ep_title}\n\nStreams included:\n")
                for sf in sorted_files:
                    out_txt.write(f"- {os.path.basename(sf)}\n")
            print(f"  [+] Generated manifest placeholder: {ep_path}.txt")

if __name__ == '__main__':
    compile_epubs()
