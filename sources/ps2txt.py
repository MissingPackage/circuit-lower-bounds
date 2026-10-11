"""Crude dvips-PostScript text extractor (no ghostscript available). Heuristic word spacing."""
import re,sys
src=open(sys.argv[1],'rb').read().decode('latin-1')
i=src.index('%%Page: 1 ')
body=src[i:]
out=[]
tok=re.compile(r'%%Page: (\S+) (\d+)|\(((?:\\.|[^\\()])*)\)|(-?\d+)\s+(-?\d+)\s+y|(-?\d+)\s+([a-zA-Z])\b|\b([a-zA-Z]{1,2})\b')
last_small=False
for m in tok.finditer(body):
    if m.group(1): out.append(f'\n\n=== PSPAGE {m.group(2)} (label {m.group(1)}) ===\n'); continue
    if m.group(3) is not None:
        s=re.sub(r'\\(\d{3})',lambda k:'{%s}'%k.group(1),m.group(3)).replace('\\(','(').replace('\\)',')')
        out.append(s); continue
    if m.group(4): out.append('\n'); continue
    if m.group(6):
        if abs(int(m.group(6)))>=22: out.append(' ')
        continue
    if m.group(8) and m.group(8) in 'ghijklmnopq' : out.append(' ')
    elif m.group(8) and m.group(8) in ('FD','FI','FF','FX','FT','p'): out.append('')
open(sys.argv[2],'w').write(''.join(out))
