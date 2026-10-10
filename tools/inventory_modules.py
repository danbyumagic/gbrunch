#!/usr/bin/env python3
"""Read module ELF metadata without executing/loading it on the host."""
import argparse, json, pathlib, struct
ROOT = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--base', type=pathlib.Path, default=ROOT/'extracted/ruby')
parser.add_argument('--output', type=pathlib.Path, default=ROOT/'evidence/module-inventory.json')
parser.add_argument('--directories', nargs='+', default=['system_dlkm_a-files', 'vendor_dlkm_a-files', 'vendor_boot_a'])
args = parser.parse_args()
base = args.base
rows = []
for directory in args.directories:
    for path in (base/directory).rglob('*.ko'):
        b = path.read_bytes()
        assert b[:5] == b'\x7fELF\x02' and b[5] == 1
        offset = struct.unpack_from('<Q', b, 40)[0]
        size, count, si = struct.unpack_from('<HHH', b, 58)
        ss = [struct.unpack_from('<IIQQQQIIQQ', b, offset+i*size) for i in range(count)]
        st = ss[si]; names = b[st[4]:st[4]+st[5]]
        sections = {names[s[0]:names.find(b'\0', s[0])].decode(): b[s[4]:s[4]+s[5]] for s in ss}
        crcs = {}
        vs = sections.get('__versions', b'')
        for i in range(0, len(vs), 64):
            name = vs[i+8:i+64].split(b'\0')[0].decode()
            crcs[name] = hex(struct.unpack_from('<Q', vs, i)[0])
        if '__version_ext_names' in sections:
            ns = sections['__version_ext_names'].rstrip(b'\0').split(b'\0')
            cs = sections['__version_ext_crcs']; assert len(ns)*4 == len(cs)
            crcs.update({n.decode(): hex(struct.unpack_from('<I', cs, i*4)[0]) for i,n in enumerate(ns)})
        rows.append({'file': str(path.relative_to(base)), 'bytes': len(b),
            'modinfo': [x.decode() for x in sections.get('.modinfo', b'').split(b'\0') if x],
            'signed': b.endswith(b'~Module signature appended~\n'),
            'symbol_crcs': crcs, 'elf_machine': struct.unpack_from('<H', b, 18)[0]})
args.output.write_text(json.dumps(rows, indent=2)+'\n')
print(json.dumps({'modules': len(rows), 'signed': sum(x['signed'] for x in rows)}))
