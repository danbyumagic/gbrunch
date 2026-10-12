#!/usr/bin/env python3
"""Audit unresolved ELF imports against actual recovery exports (no loading).

Reports symbol presence only. This is NOT a CRC/KMI/signature compatibility
certificate and must not be used to manufacture a matching Module.symvers.
"""
import argparse
import json
import pathlib
import struct


def symbols(path):
    data = path.read_bytes()
    if data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 62:
        raise ValueError(f'Expected little-endian x86_64 ELF: {path}')
    offset = struct.unpack_from('<Q', data, 40)[0]
    size, count = struct.unpack_from('<HH', data, 58)
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, offset+i*size) for i in range(count)]
    exports, imports = set(), set()
    for section in sections:
        if section[1] != 2:  # SHT_SYMTAB
            continue
        strings = sections[section[6]]
        names = data[strings[4]:strings[4]+strings[5]]
        for pos in range(section[4], section[4]+section[5], section[9]):
            name, info, other, index, value, length = struct.unpack_from('<IBBHQQ', data, pos)
            symbol = names[name:names.find(b'\0', name)].decode()
            if symbol.startswith('__ksymtab_') and index:
                exports.add(symbol[len('__ksymtab_'):])
            if symbol and index == 0 and info >> 4 == 1:  # GLOBAL; ignore optional WEAK imports
                imports.add(symbol)
    return exports, imports


def classify(imports, core, modules):
    return {'core': sorted(imports & core),
            'module_providers': {symbol: sorted(set(modules[symbol])) for symbol in sorted(imports-core) if symbol in modules},
            'missing': sorted(imports-core-modules.keys())}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--object', type=pathlib.Path, required=True)
    p.add_argument('--kernel-exports', type=pathlib.Path, required=True, help='Extracted core export CRC JSON from check_kmi.py')
    p.add_argument('--recovery-modules', type=pathlib.Path, nargs='+', required=True)
    p.add_argument('--output', type=pathlib.Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('Choose a new output file')
    core = set(json.loads(args.kernel_exports.read_text()))
    providers = {}
    for directory in args.recovery_modules:
        for module in sorted(directory.rglob('*.ko')):
            exports, _ = symbols(module)
            for symbol in exports:
                providers.setdefault(symbol, []).append(module.name)
    _, imports = symbols(args.object)
    generated = imports & {'__this_module'}
    imports -= generated
    report = {'scope': 'symbol-presence audit only; ABI and runtime admission unverified',
              'imports': len(imports), 'generated_by_modpost': sorted(generated),
              **classify(imports, core, providers),
              'abi_verified': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'imports': len(imports), 'missing': report['missing'], 'abi_verified': False}, indent=2))
    raise SystemExit(2 if report['missing'] else 0)


if __name__ == '__main__':
    main()
