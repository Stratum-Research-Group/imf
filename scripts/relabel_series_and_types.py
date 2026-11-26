"""Replace the blanket 'Series'/'Paper Type' stamp with content-derived labels."""
import glob, re, collections
PHASES = [
 (1,78,   "Phase I: Core Architecture — Lie-Algebraic Memory, Polytope Lattices, Sub-Bit Inference & MoE"),
 (79,130, "Phase II: Formal-Verification Gym & Mathematical-Physics Mappings"),
 (131,199,"Phase III: Poincaré/Hyperbolic Kernels & Machine-Certified Geometry"),
 (200,285,"Phase IV: Integrable Soliton Hierarchies (Discrete Poincaré Flows)"),
 (286,471,"Phase V: Certified-Step Scaling, Lie-Group Geometry & Kernel-Bypass I/O"),
 (472,600,"Phase VI: Blackwell Kernels, Algebraic Theorems & Direct-DMA Engines"),
]
HW="**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  "
def ptype(t):
    l=t.lower()
    if re.search(r'audit|forensic|remediation',l): return "Empirical Engineering, Forensic Audit & Architecture Rectification"
    if re.search(r'million (machine-certified )?(deductive )?steps|million steps|capstone|milestone|synthesis',l): return "Milestone Synthesis & Scaling Report"
    fused='fused' in l or 'kernel' in l and 'bypass' not in l
    cert='machine-certified' in l or 'lean 4' in l or 'machine-checked' in l
    if fused and cert: return "GPU Kernel Design + Machine-Certified Proof"
    if cert: return "Machine-Certified Formal Proof (Lean 4)"
    if re.search(r'io_uring|dma|nvme|kernel-bypass|\bring\b|shm|queue|pager|pool|prefetch|splice',l): return "Systems Engineering: Kernel-Bypass I/O Engine"
    if fused or re.search(r'blackwell|cuda|triton',l): return "GPU Kernel Design & Microbenchmark"
    if re.search(r'soliton|nls|kdv|hierarch|flow',l): return "Integrable-Systems Theory & Kernel Benchmark"
    return "Theoretical Monograph"
cnt=collections.Counter()
for f in sorted(glob.glob('papers/*.md')):
    m=re.match(r'.*/(?:paper_)?(\d+)_',f)
    if not m or 'appendix' in f: continue
    n=int(m.group(1)); s=open(f).read(); lines=s.split('\n')
    title=lines[0]; ph=next(p for a,b,p in PHASES if a<=n<=b); pt=ptype(title)
    cnt[pt]+=1
    if any(l.startswith('**Series:**') for l in lines):
        lines=[("**Series:** "+ph+"  ") if l.startswith('**Series:**') else ("**Paper Type:** "+pt+"  ") if l.startswith('**Paper Type:**') else l for l in lines]
    else:  # 596-600 used a divergent header: rebuild canonical
        end=lines.index('---')
        hdr=[title,'',HW,"**Series:** "+ph+"  ","**Paper Type:** "+pt+"  ",
             "**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  ","**Date:** November 2026  ",
             "**Status:** Peer-Review Ready — Formally Verified & Hardware Validated  ",
             "**Verification Level:** Sustained Workstation Hardware Telemetry (AMD Ryzen 5 7600X, RTX 5060 Ti, Lean 4 Core Zero External Axioms)  ",'']
        lines=hdr+lines[end:]
    open(f,'w').write('\n'.join(lines))
for k,v in cnt.most_common(): print(v,k)
