#!/usr/bin/env python3
"""Fetch pinned public ACK source and matching Clang into a private work tree.
No recovery/system image is downloaded or modified by this command.
"""
import argparse
import base64
import hashlib
import json
import pathlib
import shutil
import subprocess
import tarfile
import urllib.request

SOURCE_COMMIT = '3938c8d97142d5cf31543aa96f864a2cf832dda0'
CLANG_COMMIT = '4a7d0a5e443c27d8f68fbd46abfab464e1355a69'
CLANG_BASE = 'https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86'
SOURCE_BASE = 'https://android.googlesource.com/kernel/common'


def fetch_text_blob(url, destination, expected_git_id):
    part = destination.with_name(destination.name+'.part')
    if destination.exists():
        digest = hashlib.sha1(f'blob {destination.stat().st_size}\0'.encode())
        with destination.open('rb') as f:
            while chunk := f.read(1024**2): digest.update(chunk)
        if digest.hexdigest() == expected_git_id:
            return
        raise ValueError('Existing file does not match pinned source: '+str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as response, part.open('wb') as out:
            remainder = b''
            while chunk := response.read(1024**2):
                data = remainder+chunk
                end = len(data)//4*4
                out.write(base64.b64decode(data[:end], validate=True))
                remainder = data[end:]
            if remainder:
                raise ValueError('Truncated Gitiles base64 blob')
        digest = hashlib.sha1(f'blob {part.stat().st_size}\0'.encode())
        with part.open('rb') as f:
            while chunk := f.read(1024**2): digest.update(chunk)
        if digest.hexdigest() != expected_git_id:
            raise ValueError('Pinned Git object hash mismatch')
        part.replace(destination)
    finally:
        part.unlink(missing_ok=True)


def safe_extract(stream, root, select):
    hashes = {}
    with tarfile.open(fileobj=stream, mode='r|gz') as archive:
        for member in archive:
            path = pathlib.PurePosixPath(member.name)
            if not path.parts:
                continue
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe source archive path')
            if not member.isfile() or not select(path):
                continue
            target = root/path
            if not target.resolve().is_relative_to(root.resolve()):
                raise ValueError('Source archive path escapes work directory')
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as src, target.open('wb') as dest:
                digest = hashlib.sha256()
                for chunk in iter(lambda: src.read(1024**2), b''):
                    digest.update(chunk)
                    dest.write(chunk)
                hashes[str(path)] = digest.hexdigest()
            target.chmod(member.mode & 0o777)
    return hashes


def source_selection(path):
    return (len(path.parts) == 1 or path.name.startswith(('Kconfig','Makefile')) or
            path.parts[0] in {'include','scripts','kernel','lib','certs','LICENSES'} or
            (path.parts[0] == 'arch' and len(path.parts)>1 and path.parts[1] in {'x86','um'}) or
            str(path).startswith(('drivers/gpu/', 'drivers/android/', 'tools/objtool/',
                                  'tools/build/', 'tools/include/', 'tools/lib/',
                                  'tools/arch/', 'tools/scripts/')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=pathlib.Path, required=True)
    parser.add_argument('--source-archive', type=pathlib.Path, help='Reuse the pinned downloaded source archive')
    parser.add_argument('--clang-only', action='store_true')
    parser.add_argument('--full-source', action='store_true', help='Extract full ACK source for a replacement-kernel build')
    args = parser.parse_args()
    root = args.work.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < 2*1024**3:
        raise ValueError('Need at least 2 GiB free for source/compiler inputs; builds require additional space')
    clang = root/'clang-r584948c'
    compiler_url = f'{CLANG_BASE}/+/{CLANG_COMMIT}/clang-r584948c'
    with urllib.request.urlopen(compiler_url+'/bin/?format=JSON', timeout=45) as r:
        entries = json.loads(r.read().decode().split('\n',1)[1])['entries']
    selected = {'clang-22','lld','llvm-ar','llvm-nm','llvm-objcopy','llvm-objdump','llvm-readobj'}
    for entry in entries:
        if entry['name'] not in selected:
            continue
        path = clang/'bin'/entry['name']
        print('Fetching pinned '+entry['name'], flush=True)
        fetch_text_blob(compiler_url+'/bin/'+entry['name']+'?format=TEXT', path, entry['id'])
        path.chmod(0o755)
    for name, target in {'clang':'clang-22','clang-real':'clang-22','ld.lld':'lld',
                         'llvm-ranlib':'llvm-ar','llvm-readelf':'llvm-readobj','llvm-strip':'llvm-objcopy'}.items():
        path = clang/'bin'/name
        if not path.exists(): path.symlink_to(target)
    with urllib.request.urlopen(compiler_url+'/lib/?format=JSON', timeout=45) as r:
        libraries = json.loads(r.read().decode().split('\n',1)[1])['entries']
    for entry in libraries:
        if entry['name'] == 'libxml2.so.16':
            if entry['mode'] == 40960:
                raise ValueError('Pinned libxml2 unexpectedly changed into a symlink')
            fetch_text_blob(compiler_url+'/lib/'+entry['name']+'?format=TEXT', clang/'lib'/entry['name'], entry['id'])
    with urllib.request.urlopen(compiler_url+'/?format=JSON', timeout=45) as r:
        entries = json.loads(r.read().decode().split('\n',1)[1])['entries']
    for entry in entries:
        if entry['type']=='blob':
            fetch_text_blob(compiler_url+'/'+entry['name']+'?format=TEXT', clang/entry['name'], entry['id'])
    with urllib.request.urlopen(f'{CLANG_BASE}/+archive/{CLANG_COMMIT}/clang-r584948c/lib/clang/22/include.tar.gz', timeout=60) as r:
        safe_extract(r, clang/'lib/clang/22/include', lambda path: True)
    if not args.clang_only:
        archive = args.source_archive or root/'android-common.tar.gz'
        if not archive.exists():
            with urllib.request.urlopen(f'{SOURCE_BASE}/+archive/{SOURCE_COMMIT}.tar.gz', timeout=60) as r, archive.open('wb') as out:
                shutil.copyfileobj(r, out, 1024**2)
        expected = json.loads((pathlib.Path(__file__).resolve().parents[1]/'docs/amd/source-evidence.json').read_text())['source_archive']['sha256']
        if hashlib.file_digest(archive.open('rb'),'sha256').hexdigest() != expected:
            raise ValueError('Source archive does not match the inspected exact-source archive')
        if (root/'source').exists():
            raise ValueError('Source directory exists; do not overwrite an active build')
        with archive.open('rb') as r:
            files = safe_extract(r, root/'source', (lambda path: True) if args.full_source else source_selection)
        (root/'source/gbrunch-source-files.json').write_text(json.dumps({'source_commit':SOURCE_COMMIT, 'source_archive_sha256':expected, 'files':files}, sort_keys=True)+'\n')
    version = subprocess.check_output([str(clang/'bin/clang-22'),'--version'], text=True)
    (root/'inputs.json').write_text(json.dumps({'source_commit':SOURCE_COMMIT,'clang_commit':CLANG_COMMIT,
        'clang_version':version,'scope':'full ACK kernel source' if args.full_source else 'AMDGPU source/object build inputs; not a full replacement-kernel source checkout'}, indent=2)+'\n')
    print(version)

if __name__ == '__main__': main()
