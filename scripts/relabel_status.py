"""Derive Status / Verification Level from evidence actually present in each paper."""
import glob,re,collections
c=collections.Counter()
for f in sorted(glob.glob('papers/*.md')):
    s=open(f).read(); L=s.split('\n')
    if not any(l.startswith('**Status:**') for l in L): continue
    lean=bool(re.search(r'```lean|\w+\.lean',s))
    bench=bool(re.search(r'^\|.*(µs|μs|\\mu|\bms\b|GB/s|speedup)',s,re.M|re.I)) or bool(re.search(r'csrc/|\.cu\b|\.cpp\b',s))
    ev=[]; 
    if lean: ev.append("Lean 4 source shown or referenced in text")
    if bench: ev.append("benchmark figures or kernel source reported (AMD Ryzen 5 7600X, RTX 5060 Ti)")
    if ev: st="Evidence Included — Not Independently Reviewed"; vl="; ".join(ev)
    else:  st="Theoretical Draft — No Machine Proof or Benchmark in Text"; vl="None (derivation only)"
    c[(lean,bench)]+=1
    out=[]
    for l in L:
        if l.startswith('**Status:**'): l="**Status:** "+st+"  "
        elif l.startswith('**Verification Level:**'): l="**Verification Level:** "+vl+"  "
        out.append(l)
    open(f,'w').write('\n'.join(out))
print(c)
