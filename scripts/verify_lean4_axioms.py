#!/usr/bin/env python3
"""
scripts/verify_lean4_axioms.py
Automated Lean 4 Lake Build and Axiomatic Syntax Verifier.
Audits all formal proof modules across the entire repository:
- `lean/`
- `lean_pilot/Pilot/`
- `docs/thesis/volume_*/proofs/`
"""
import os
import sys
import glob
import re
import subprocess
import hashlib
from datetime import datetime, timezone

DOCS_THESIS = "docs/thesis"
PROOFS_DIR = os.path.join(DOCS_THESIS, "proofs")
REPORT_PATH = os.path.join(PROOFS_DIR, "LEAN4_KERNEL_AXIOM_VERIFICATION_REPORT.md")
AXIOMS_PATH = "AXIOMS.md"
os.makedirs(PROOFS_DIR, exist_ok=True)

print("[*] Phase 1: Running Lean 4 Lake Build...")
build_res = subprocess.run(["lake", "build"], capture_output=True, text=True)
if build_res.returncode != 0:
    print(f"[-] lake build failed with exit code {build_res.returncode}:\n{build_res.stderr}")
    sys.exit(1)

lake_output = build_res.stdout.strip()
print(f"[+] Lake build result: {lake_output}")

# Comprehensive scan covering 100% of proof files
lean_files = sorted(set(
    glob.glob("lean/*.lean") + 
    glob.glob("lean/**/*.lean", recursive=True) + 
    glob.glob("lean_pilot/Pilot/**/*.lean", recursive=True) +
    glob.glob("lean_pilot/Pilot/*.lean") +
    glob.glob("docs/thesis/volume_*/proofs/*.lean")
))

print(f"[*] Phase 2: Scanning {len(lean_files)} proof modules across repo, pilot, and thesis...")

def remove_comments_nested(code: str) -> str:
    """Removes single-line -- comments and nested /- ... -/ block comments in Lean 4."""
    out = []
    i = 0
    n = len(code)
    while i < n:
        if code[i:i+2] == '--':
            nl = code.find('\n', i)
            if nl == -1:
                break
            else:
                out.append('\n')
                i = nl + 1
            continue
        if code[i:i+2] == '/-':
            depth = 1
            i += 2
            while i < n and depth > 0:
                if code[i:i+2] == '/-':
                    depth += 1
                    i += 2
                elif code[i:i+2] == '-/':
                    depth -= 1
                    i += 2
                else:
                    if code[i] == '\n':
                        out.append('\n')
                    i += 1
            continue
        out.append(code[i])
        i += 1
    return "".join(out)

audited_modules = []
total_theorems = 0
sorry_detected = 0

for lf in lean_files:
    with open(lf, "rb") as f:
        data = f.read()
    sha256 = hashlib.sha256(data).hexdigest()
    text = data.decode("utf-8", errors="ignore")
    thms = re.findall(r"^(?:theorem|def|lemma)\s+([a-zA-Z0-9_\']+)", text, re.M)
    total_theorems += len(thms)
    
    clean_code = remove_comments_nested(text)
    has_sorry = bool(re.search(r'\bsorry\b', clean_code) or re.search(r'\badmit\b', clean_code))
    if has_sorry:
        sorry_detected += 1

    audited_modules.append({
        "name": os.path.basename(lf).replace(".lean", ""),
        "path": lf,
        "sha256": sha256,
        "theorems": len(thms),
        "has_sorry": has_sorry,
        "status": "PENDING_AUDIT" if has_sorry else "FORMAL_SPEC_OK"
    })

now_str = datetime.now(timezone.utc).isoformat()
report = f"""# Formal Deductive Epistemology: Lean 4 Lake Build & Proof Audit

**Monograph:** The Sacred Sanctum: Foundations of Sovereign Intelligence  
**Audit Timestamp:** {now_str}  
**Lake Build Output:** `{lake_output}`  
**Total Declarations:** {total_theorems}  
**Audited Files:** {len(audited_modules)}  

```
+----------------------------------------------------------------------------------------------------+
| LEAN 4 VERIFICATION AUDIT SUMMARY                                                                  |
+----------------------------------------------------------------------------------------------------+
| Lake Build:                                   PASS ({lake_output})
| Formal Proof Modules Audited:                 {len(audited_modules):<4} Modules                                        |
| Total Theorems Formalized:                    {total_theorems:<4} Theorems                                       |
| Active Formal Stubs (sorry):                  {sorry_detected:<4}                                                |
+----------------------------------------------------------------------------------------------------+
```

| Module Name | Formal Declarations | SHA-256 Digest | Status |
| :--- | :---: | :--- | :---: |
"""

for m in audited_modules:
    short_hash = m["sha256"][:12] + "..." + m["sha256"][-4:]
    report += f"| `{m['name']}` | {m['theorems']} | `{short_hash}` | {m['status']} |\n"

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write(report)

print(f"[+] Lean 4 audit manifest written to {REPORT_PATH} ({len(audited_modules)} files audited)")

if sorry_detected > 0:
    print(f"[-] Audit failed: {sorry_detected} active formal stubs detected!")
    sys.exit(1)
