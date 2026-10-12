#!/usr/bin/env python3
"""Verify listed source bytes against the pinned AMD build input manifest.

This checks manifest metadata and file hashes. It does not authenticate a
user-modified manifest with a cryptographic signature.
"""
import hashlib
import json
import pathlib
import stat


SOURCE_COMMIT = '3938c8d97142d5cf31543aa96f864a2cf832dda0'
SOURCE_ARCHIVE_SHA256 = 'd9cdb66cf162a1c965d7d10fc52e0189b8be219f43b1e305ce40004e0395b1e9'
MANIFEST_NAME = 'gbrunch-source-files.json'


def _regular_nonsymlink(path: pathlib.Path) -> bool:
    try:
        mode = path.lstat().st_mode
    except OSError:
        return False
    return stat.S_ISREG(mode)


def _is_header_overlay(relative: pathlib.PurePosixPath) -> bool:
    parts = relative.parts
    return (parts[0] == 'include' or
            (len(parts) >= 3 and parts[:3] == ('arch', 'x86', 'include')))


def verify_source_manifest(root: pathlib.Path, *, header_overlay: bool = False) -> int:
    """Verify the pinned manifest and its listed files; return verified count.

    With ``header_overlay=True``, recovery-generated ``include/`` and
    ``arch/x86/include/`` files may differ and are excluded from hashing.
    Driver source files remain subject to verification.
    """
    root = pathlib.Path(root).resolve()
    manifest = root / MANIFEST_NAME
    if not _regular_nonsymlink(manifest):
        raise ValueError(f'Missing or unsafe source manifest: {manifest}')
    try:
        data = json.loads(manifest.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid source manifest JSON') from exc
    if not isinstance(data, dict):
        raise ValueError('Source manifest must be a JSON object')
    if data.get('source_commit') != SOURCE_COMMIT:
        raise ValueError('Source manifest commit does not match the pinned ACK revision')
    if data.get('source_archive_sha256') != SOURCE_ARCHIVE_SHA256:
        raise ValueError('Source manifest archive hash does not match the pinned archive')
    files = data.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('Source manifest files must be a non-empty object')

    verified = 0
    for name, expected in files.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            raise ValueError('Source manifest file paths and hashes must be strings')
        relative = pathlib.PurePosixPath(name)
        if (not name or relative.is_absolute() or '\\' in name or
                any(part in ('', '.', '..') for part in relative.parts)):
            raise ValueError(f'Unsafe source manifest path: {name!r}')
        if len(expected) != 64 or any(ch not in '0123456789abcdef' for ch in expected):
            raise ValueError(f'Invalid SHA256 for source file: {name}')
        if header_overlay and _is_header_overlay(relative):
            continue

        path = root.joinpath(*relative.parts)
        cursor = root
        for part in relative.parts:
            cursor = cursor / part
            try:
                mode = cursor.lstat().st_mode
            except OSError as exc:
                raise ValueError(f'Missing source file: {name}') from exc
            if stat.S_ISLNK(mode):
                raise ValueError(f'Symlink in source path: {name}')
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError(f'Source path is not a regular file: {name}')
        if not path.resolve().is_relative_to(root):
            raise ValueError(f'Source path escapes source root: {name}')
        digest = hashlib.sha256()
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError(f'Source file hash mismatch: {name}')
        verified += 1
    return verified
