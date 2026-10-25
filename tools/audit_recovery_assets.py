#!/usr/bin/env python3
"""Read-only compatibility gate for a pinned recovery and existing assembler assets.

Reports kernel/module/offset mismatches; never patches modules or recovery bytes.
A passing byte audit is not an Android or physical hardware boot guarantee.
"""
import argparse,hashlib,json,pathlib,struct,subprocess
from inspect_recovery import gpt,liblp
from prepare_recovery_profile import load_profile,sha,regular


def find_module(dump_erofs,raw,filename,sources):
    for name in ['system_dlkm_a','vendor_dlkm_a']:
        result=subprocess.run([str(dump_erofs),'--offset='+str(sources[name]),
            '--path=/lib/modules/'+filename,'--cat',str(raw)],capture_output=True)
        # A missing path can return zero with empty stdout in dump.erofs.
        if result.returncode==0 and result.stdout.startswith(b'\x7fELF'):
            return {'source':name,'actual_sha256':hashlib.sha256(result.stdout).hexdigest()}
    return None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['profile','raw','assets','dump-erofs','output']:
        p.add_argument('--'+name,required=True,type=pathlib.Path)
    a=p.parse_args();profile=load_profile(a.profile)
    regular(a.raw)
    if a.output.exists() or a.output.is_symlink():raise ValueError('Output must be new')
    if a.raw.stat().st_size!=profile['raw_bytes'] or sha(a.raw)!=profile['raw_sha256']:
        raise ValueError('Raw recovery does not match the selected profile')
    assets=json.loads(a.assets.read_text())
    with a.raw.open('rb') as f:
        parts=gpt(f);by={x['name']:x for x in parts}
        f.seek(by['boot_a']['offset']);header=f.read(4096)
        if header[:8]!=b'ANDROID!':raise ValueError('Unexpected boot image format')
        size=struct.unpack_from('<I',header,8)[0]
        if size>by['boot_a']['bytes']-4096:raise ValueError('Kernel outside boot partition')
        kernel=f.read(size);kernel_hash=hashlib.sha256(kernel).hexdigest()
        logical=liblp(f,by['super']['offset'])['slots'][0]['partitions']
    sources={}
    for name in ['system_dlkm_a','vendor_dlkm_a','vendor_a']:
        part=next(x for x in logical if x['name']==name)
        if len(part['extents'])!=1 or part['extents'][0]['target_type']!=0:
            raise ValueError('Audit requires a single linear '+name+' extent')
        sources[name]=part['extents'][0]['absolute_offset']
    modules=[]
    for m in assets['modules']:
        row={'file':m['file'],'expected_sha256':m['sha256'],'matches':False}
        found=find_module(a.dump_erofs,a.raw,m['file'],sources)
        if found:
            row.update(found);row['matches']=found['actual_sha256']==m['sha256']
        modules.append(row)
    report={'scope':'exact kernel and first-stage module byte compatibility only; not vendor HAL/policy or runtime certification',
            'build':profile['build'],'version':profile['version'],'kernel_sha256':kernel_hash,
            'expected_asset_kernel_sha256':assets['google_kernel_sha256'],
            'kernel_matches':kernel_hash==assets['google_kernel_sha256'],
            'logical_source_offsets':sources,'modules':modules}
    report['existing_kernel_module_assets_match']=report['kernel_matches'] and all(m['matches'] for m in modules)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='modules'},indent=2))
    raise SystemExit(0 if report['existing_kernel_module_assets_match'] else 2)

if __name__=='__main__':main()
