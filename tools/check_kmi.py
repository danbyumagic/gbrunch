#!/usr/bin/env python3
"""Compare imported MODVERSIONS CRCs against the actual extracted kernel exports.

Not-in-core imports may be supplied by other modules; this is not a full depmod
or protected-symbol/signature admission test.
"""
import json, pathlib, struct
ROOT = pathlib.Path(__file__).resolve().parents[1]
b = (ROOT/'extracted/ruby/vmlinux').read_bytes()
off = struct.unpack_from('<Q', b, 40)[0]
size, count, strings_index = struct.unpack_from('<HHH', b, 58)
sections = [struct.unpack_from('<IIQQQQIIQQ', b, off+i*size) for i in range(count)]
st = sections[strings_index]
names = b[st[4]:st[4]+st[5]]
sections = {names[s[0]:names.find(b'\0', s[0])].decode(): s for s in sections}
s, c, strings = (sections[n] for n in ('__ksymtab', '__kcrctab', '__ksymtab_strings'))
assert s[5]//12 == c[5]//4
crcs = {}
for i in range(s[5]//12):
    ptr = s[3]+i*12+4+struct.unpack_from('<i', b, s[4]+i*12+4)[0]
    p = strings[4]+ptr-strings[3]
    assert strings[4] <= p < strings[4]+strings[5]
    name = b[p:b.find(b'\0', p)].decode()
    crcs[name] = hex(struct.unpack_from('<I', b, c[4]+i*4)[0])
(ROOT/'evidence/kernel-symbol-crcs.json').write_text(json.dumps(crcs, indent=2)+'\n')
results = []
for m in json.loads((ROOT/'evidence/module-inventory.json').read_text()):
    matches, bad, external = 0, {}, []
    for name, value in m['symbol_crcs'].items():
        if name not in crcs:
            external.append(name)
        elif int(value, 16) == int(crcs[name], 16):
            matches += 1
        else:
            bad[name] = {'module': value, 'kernel': crcs[name]}
    results.append({'file': m['file'], 'core_matches': matches,
                    'core_mismatches': bad, 'not_in_core': external})
(ROOT/'evidence/module-kmi-comparison.json').write_text(json.dumps(results, indent=2)+'\n')
print(json.dumps({'exports': len(crcs), 'modules': len(results),
                  'core_matches': sum(m['core_matches'] for m in results),
                  'core_mismatches': sum(len(m['core_mismatches']) for m in results)}))
