import glob
import re

files = sorted(glob.glob("docs/thesis/volume_*/chapter_*.md"))
found_unproven = []

for fpath in files:
    with open(fpath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    in_code = False
    for idx, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            in_code = not in_code
        if in_code and re.search(r'\bsorry\b', line):
            found_unproven.append((fpath, idx, line.strip()))

if found_unproven:
    print(f"[!] Found {len(found_unproven)} raw sorry statements inside code blocks:")
    for path, idx, line in found_unproven:
        print(f"  {path}:{idx} -> {line}")
else:
    print("[+] ZERO sorry statements detected across all chapter code blocks in the entire trilogy!")
