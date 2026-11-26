"""Insert a visible notice into every paper whose Status is 'Theoretical Draft'."""
import glob
MARK="<!-- THEORETICAL-DRAFT-NOTICE -->"
NOTICE=(MARK+"\n> **⚠ THEORETICAL DRAFT.** This paper contains no machine-checked proof (Lean 4) and no reported "
"benchmark or kernel source. Its claims are theoretical derivations or design proposals and have **not** been "
"formally verified, experimentally validated, or independently reviewed. Treat all results as unverified.\n")
n=0; drafts=[]
for f in sorted(glob.glob('papers/*.md')):
    s=open(f).read()
    if '**Status:** Theoretical Draft' not in s: continue
    drafts.append(f)
    if MARK in s: continue
    i=s.index('\n---\n')+5
    s=s[:i]+"\n"+NOTICE+s[i:]; open(f,'w').write(s); n+=1
open('papers/THEORETICAL_DRAFTS.md','w').write("# Theoretical Drafts\n\nPapers below have no in-text Lean proof or benchmark and are unverified.\n\n"+"\n".join(f"- [{x.split('/')[-1]}]({x.split('/')[-1]})" for x in drafts)+"\n")
print(n,len(drafts))
