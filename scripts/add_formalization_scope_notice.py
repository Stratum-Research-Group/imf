"""Flag papers whose referenced Lean files use core Lean only (no Mathlib): abstract-model checks, not the full classical theorem."""
import re,glob,os
MARK="<!-- FORMALIZATION-SCOPE-NOTICE -->"
N=(MARK+"\n> **ℹ FORMALIZATION SCOPE.** The Lean 4 files referenced by this paper contain no `sorry`, but they import core Lean only "
"(no Mathlib definitions of the objects named in the title). They check statements about a simplified, abstract model; "
"they do **not** establish the full classical theorem or physical claim named in the title.\n")
force={'paper_593','paper_596'}
n=0
for f in sorted(glob.glob('papers/phase_*/*.md')):
    s=open(f).read()
    if MARK in s: continue
    refs=[r for r in set(re.findall(r'([A-Za-z0-9_]+)\.lean',s)) if os.path.exists(f'lean/{r}.lean')]
    toy=bool(refs) and not any(re.search(r'^import Mathlib',open(f'lean/{r}.lean').read(),re.M) for r in refs)
    key=os.path.basename(f)[:9]
    if not (toy or key in force): continue
    L=s.split('\n')
    if key in force:
        L[0]=L[0].replace('Machine-Certified','Abstract-Model Formal Check of')
    out=[]
    for l in L:
        if l.startswith('**Paper Type:** Machine-Certified') or l.startswith('**Paper Type:** GPU Kernel Design + Machine-Certified'):
            l=l.replace('Machine-Certified Formal Proof (Lean 4)','Abstract-Model Formal Check (Lean 4, core only)').replace('Machine-Certified Proof','Abstract-Model Formal Check')
        if l.startswith('**Verification Level:**') and 'Lean 4 source' in l:
            l=l.replace('Lean 4 source shown or referenced in text','Lean 4 abstract-model check (core Lean, no Mathlib)')
        out.append(l)
    s='\n'.join(out); i=s.index('\n---\n')+5
    open(f,'w').write(s[:i]+"\n"+N+s[i:]); n+=1
print(n)
