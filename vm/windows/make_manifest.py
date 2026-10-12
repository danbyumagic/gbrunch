#!/usr/bin/env python3
"""Describe existing locally assembled VM files; does not download/build images."""
import argparse
import hashlib
import json
from pathlib import Path
from launch import regular

parser = argparse.ArgumentParser(description=__doc__)
for key in ('kernel', 'initrd', 'cmdline', 'disk'):
    parser.add_argument('--' + key, required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
output = args.output.resolve()
if output.exists():
    parser.error('Choose a new output path')
assets = {}
for key in ('kernel', 'initrd', 'cmdline', 'disk'):
    path = regular(getattr(args, key))
    try:
        relative = path.relative_to(output.parent)
    except ValueError:
        parser.error('Place the prepared assets together under the output manifest directory')
    entry = {'file': relative.as_posix()}
    if key != 'disk':
        with path.open('rb') as stream:
            entry['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    assets[key] = entry
output.write_text(json.dumps({'profile_version': 1, 'assets': assets,
                             'status': 'experimental; desktop and Windows unverified'}, indent=2) + '\n')
print(f'Created {output}. The launcher still requires a standalone QCOW2 base with no backing chain.')
