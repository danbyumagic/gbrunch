#!/usr/bin/env python3
"""Read back a disposable probe file without mounting anything on the host."""
import hashlib,json,pathlib,subprocess,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'tools'))
from inspect_recovery import gpt


def verify(work, debugfs):
    work=pathlib.Path(work).resolve()
    image=work/'one-partition.raw';original=work/'system.ext4'
    if not image.is_file() or not original.is_file() or str(work).startswith('/dev/'):
        raise ValueError('Expected an existing regular-file fixture directory')
    with image.open('rb') as source:
        parts=gpt(source)
        if len(parts)!=1:raise ValueError('Expected one outer partition')
        part=parts[0]
        if not 0<part['bytes']<=1<<30 or part['offset']+part['bytes']>image.stat().st_size:
            raise ValueError('Unexpected fixture bounds')
        source.seek(part['offset'])
        host=work/'readback-host.ext4'
        with host.open('xb') as out:
            left=part['bytes']
            while left:
                chunk=source.read(min(left,1<<20))
                if not chunk:raise ValueError('Short fixture read')
                out.write(chunk);left-=len(chunk)
    inner=work/'readback-googlebook.img'
    if inner.exists():raise ValueError('Readback destination already exists')
    # debugfs has its own command parser: keep the output argument a fixed basename.
    subprocess.run([str(pathlib.Path(debugfs).resolve()),'-R',
                    'dump /googlebook.img readback-googlebook.img',host.name],
                   cwd=work,check=True,stdout=subprocess.DEVNULL)
    with inner.open('rb') as source:
        parts=gpt(source)
        if len(parts)!=2:raise ValueError('Expected two inner partitions')
        system=parts[0]
        if system['bytes']!=original.stat().st_size:raise ValueError('System fixture size differs')
        source.seek(system['offset']);digest=hashlib.sha256();left=system['bytes']
        while left:
            chunk=source.read(min(left,1<<20))
            if not chunk:raise ValueError('Short system read')
            digest.update(chunk);left-=len(chunk)
    with original.open('rb') as source:expected=hashlib.file_digest(source,'sha256').hexdigest()
    if digest.hexdigest()!=expected:raise ValueError('System fixture was modified')
    return {'outer_gpt_crc_verified':True,'nested_gpt_crc_verified':True,
            'system_partition_bytes_unchanged':True,'system_sha256':expected}
