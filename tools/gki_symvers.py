#!/usr/bin/env python3
"""Build a Module.symvers for out-of-tree modules from the stock Googlebook kernel and modules.

vmlinux exports come from __ksymtab/__kcrctab/__ksymtab_strings (the CRCs the running kernel
checks). Module exports come from the stock modules' own __ksymtab_* symbols, with CRCs taken
from __versions/__version_ext_* of stock modules that import them. A module export that no stock
module imports has no proven CRC and is omitted, so modpost reports it as undefined instead of
guessing. Inputs are read only.

  gki_symvers.py --vmlinux vmlinux --modules DIR [DIR...] --out Module.symvers [--report r.json]
"""
import argparse,json,pathlib,struct,subprocess

def elf_sections(b):
    assert b[:4]==b'\x7fELF' and b[4]==2,'need ELF64'
    off=struct.unpack_from('<Q',b,40)[0];size,count,stridx=struct.unpack_from('<HHH',b,58)
    raw=[struct.unpack_from('<IIQQQQIIQQ',b,off+i*size) for i in range(count)]
    names=b[raw[stridx][4]:raw[stridx][4]+raw[stridx][5]]
    return {names[s[0]:names.find(b'\0',s[0])].decode():s for s in raw}

def cstr(b,p):return b[p:b.find(b'\0',p)].decode()

def vmlinux_exports(path):
    b=path.read_bytes();sec=elf_sections(b)
    ks,kc,st=(sec[n] for n in ('__ksymtab','__kcrctab','__ksymtab_strings'))
    n=ks[5]//12;assert kc[5]//4==n,'ksymtab/kcrctab mismatch'
    out={}
    for i in range(n):
        base=ks[3]+i*12
        def target(field):
            rel=struct.unpack_from('<i',b,ks[4]+i*12+field)[0]
            return base+field+rel
        name=cstr(b,st[4]+target(4)-st[3])
        nsrel=struct.unpack_from('<i',b,ks[4]+i*12+8)[0]
        ns=cstr(b,st[4]+target(8)-st[3]) if nsrel else ''
        out[name]={'crc':struct.unpack_from('<I',b,kc[4]+i*4)[0],'module':'vmlinux','ns':ns}
    return out

def module_imports(path):
    """(name,crc) pairs a stock module was linked against."""
    b=path.read_bytes();sec=elf_sections(b);pairs=[]
    if '__version_ext_crcs' in sec and '__version_ext_names' in sec:
        c,nm=sec['__version_ext_crcs'],sec['__version_ext_names']
        names=b[nm[4]:nm[4]+nm[5]].split(b'\0')
        crcs=[struct.unpack_from('<I',b,c[4]+i*4)[0] for i in range(c[5]//4)]
        pairs+=list(zip([x.decode() for x in names if x],crcs))
    if '__versions' in sec:
        v=sec['__versions']
        for i in range(v[5]//64):
            e=b[v[4]+i*64:v[4]+i*64+64];crc=struct.unpack_from('<Q',e)[0]&0xffffffff
            pairs.append((e[8:].split(b'\0')[0].decode(),crc))
    return pairs

def module_exports(path):
    out=subprocess.run(['nm','--defined-only',str(path)],capture_output=True,text=True,check=True).stdout
    return {l.split()[-1][len('__ksymtab_'):] for l in out.splitlines() if l.split()[-1].startswith('__ksymtab_')}

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--vmlinux',required=True,type=pathlib.Path)
    p.add_argument('--modules',nargs='+',required=True,type=pathlib.Path)
    p.add_argument('--out',required=True,type=pathlib.Path)
    p.add_argument('--report',type=pathlib.Path)
    a=p.parse_args()
    table=vmlinux_exports(a.vmlinux)
    kos=sorted(k for d in a.modules for k in d.rglob('*.ko'))
    seen={};conflicts=[]
    for k in kos:
        for name,crc in module_imports(k):
            if name in seen and seen[name]!=crc:conflicts.append(name)
            seen.setdefault(name,crc)
    core_mismatch=[n for n,c in seen.items() if n in table and table[n]['crc']!=c]
    unproven=[]
    for k in kos:
        for name in module_exports(k):
            if name in table:continue
            if name in seen:table[name]={'crc':seen[name],'module':str(k.with_suffix('')).rsplit('/lib/modules/',1)[-1],'ns':''}
            else:unproven.append((name,k.name))
    if conflicts or core_mismatch:raise SystemExit('CRC disagreement: %s %s'%(sorted(set(conflicts))[:10],core_mismatch[:10]))
    lines=['0x%08x\t%s\t%s\tEXPORT_SYMBOL_GPL\t%s'%(v['crc'],n,v['module'],v['ns']) for n,v in sorted(table.items())]
    a.out.write_text('\n'.join(lines)+'\n')
    rep={'vmlinux_exports':sum(v['module']=='vmlinux' for v in table.values()),
         'module_exports_with_crc':sum(v['module']!='vmlinux' for v in table.values()),
         'module_exports_without_proven_crc':len(unproven),'stock_modules_scanned':len(kos)}
    if a.report:a.report.write_text(json.dumps(dict(rep,unproven=sorted(unproven)),indent=1)+'\n')
    print(json.dumps(rep,indent=1))

if __name__=='__main__':main()
