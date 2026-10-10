#!/usr/bin/env python3
"""Local-only Android first-stage Xe integration. Never writes a recovery/device.

Original boot fragments stay unchanged; the added CPIO carries original GPL Xe
modules, pinned driver firmware and independently generated fstab/module lists.
The resulting ramdisk includes Google components and must not be distributed.
"""
import gzip, hashlib, json, pathlib, stat

R = pathlib.Path(__file__).resolve().parents[1]
O = R / 'build/native-android-gpu'
O.mkdir(exist_ok=True)


def entry(name, data, mode, inode):
    name = name.encode() + b'\0'
    fields = [inode, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name), 0]
    value = b'070701' + b''.join(f'{n:08x}'.encode() for n in fields) + name
    value += bytes(-len(value) % 4)
    value += data + bytes(-len(data) % 4)
    return value


def build():
    stage = R / 'build/xe-probe'
    manifest = json.loads((stage / 'manifest.json').read_text())
    records = json.loads((R / 'evidence/module-inventory.json').read_text())
    metadata = {r['file']: r for r in records}
    modules = manifest['modules']
    filenames = {m['name']: m['file'] for m in modules}
    entries = {}
    deps = []
    aliases = []
    for m in modules:
        source = stage / 'modules' / m['file']
        b = source.read_bytes()
        assert hashlib.sha256(b).hexdigest() == m['sha256']
        entries['lib/modules/' + m['file']] = (stat.S_IFREG | 0o644, b)
        info = metadata[m['source']]['modinfo']
        names = next((x[8:] for x in info if x.startswith('depends=')), '').split(',')
        depends = ['lib/modules/' + filenames[n.replace('-', '_')] for n in names if n]
        deps.append('/lib/modules/' + m['file'] + ':' + ((' ' + ' '.join('/' + n for n in depends)) if depends else ''))
        aliases.extend('alias ' + x[6:] + ' ' + m['name'] for x in info if x.startswith('alias='))
    for m in manifest['firmware']:
        b = (stage / 'firmware' / m['name']).read_bytes()
        assert hashlib.sha256(b).hexdigest() == m['sha256']
        entries['lib/firmware/' + m['name']] = (stat.S_IFREG | 0o644, b)
    for name in ['modules.load', 'modules.load.recovery']:
        entries['lib/modules/' + name] = (stat.S_IFREG | 0o644, ('\n'.join(m['file'] for m in modules) + '\n').encode())
    for name, data in [('modules.dep', '\n'.join(deps)), ('modules.alias', '\n'.join(aliases)),
                       ('modules.softdep', ''), ('modules.options', '')]:
        entries['lib/modules/' + name] = (stat.S_IFREG | 0o644, (data + '\n').encode())
    fstab = (R / 'build/vendor-view/fstab.android-desktop').read_bytes()
    entries['first_stage_ramdisk/fstab.android-desktop'] = (stat.S_IFREG | 0o644, fstab)
    entries['gbrunchlogs'] = (stat.S_IFDIR | 0o755, b'')
    for name in ['lib', 'lib/modules', 'lib/firmware', 'lib/firmware/i915']:
        entries[name] = (stat.S_IFDIR | 0o755, b'')
    extra = b''.join(entry(n, b, mode, 970000 + i) for i, (n, (mode, b)) in enumerate(sorted(entries.items())))
    extra += entry('TRAILER!!!', b'', 0, 979999)
    (O / 'xe-first-stage-overlay.cpio').write_bytes(extra)
    fragments = [R / 'extracted/ruby' / p for p in [
        'vendor_boot_a/fragment-0-platform.cpio', 'vendor_boot_a/fragment-2-dlkm.cpio',
        'init_boot_a/ramdisk.cpio']]
    blob = b''.join(p.read_bytes() for p in fragments) + extra
    (O / 'initrd.gz').write_bytes(gzip.compress(blob, mtime=0))
    result = {'scope': 'local-only first-stage integration, not HP-ready Android image',
              'original_fragments': {str(p.relative_to(R)): hashlib.sha256(p.read_bytes()).hexdigest() for p in fragments},
              'added_modules': [m['file'] for m in modules],
              'added_firmware': manifest['firmware'],
              'initrd_sha256': hashlib.sha256((O / 'initrd.gz').read_bytes()).hexdigest(),
              'system_partitions': 'unchanged', 'vendor': 'independent GBVENDOR experiment',
              'physical_android': 'not tested', 'distribution': 'scripts only; never package resulting Google ramdisk'}
    (O / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    build()
