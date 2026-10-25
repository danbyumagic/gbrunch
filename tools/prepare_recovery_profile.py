#!/usr/bin/env python3
"""Fetch a pinned experimental recovery into private regular files; never install.

Legacy v0.3 assemblers/assets remain pinned separately. A new profile is not
proof that those assets can be used with the new recovery.
"""
import argparse,hashlib,json,pathlib,re,shutil,subprocess,sys,urllib.request,zipfile


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def load_profile(path):
    profile=json.loads(pathlib.Path(path).read_text())
    build=str(profile['build'])
    if not re.fullmatch(r'\d+',build) or profile['device']!='ruby':
        raise ValueError('Only an explicit Lenovo Ruby build profile is supported')
    if profile['url']!=f'https://dl.google.com/device/recovery/ruby-user/{build}/recovery.zip':
        raise ValueError('Expected the exact official Google Ruby download URL')
    for key in ['zip_sha256','raw_sha256']:
        if not re.fullmatch(r'[0-9a-f]{64}',profile[key]):raise ValueError('Invalid pinned SHA256')
    if not isinstance(profile['raw_bytes'],int) or profile['raw_bytes']<=0:
        raise ValueError('Invalid raw image length')
    return profile


def regular(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('Refusing a symlink or non-regular cache file: '+str(path))


def prepare(profile,cache,download=False):
    cache=pathlib.Path(cache).absolute()
    if str(cache.resolve()).startswith('/dev/'):
        raise ValueError('Device directories are not cache locations')
    cache.mkdir(parents=True,exist_ok=True)
    archive=cache/'recovery.zip';raw=cache/'recovery.raw'
    for path in [archive,raw,cache/'recovery.zip.part',cache/'recovery.raw.part']:regular(path)
    if not archive.exists():
        if not download:raise ValueError('Archive absent; explicitly use --download')
        part=cache/'recovery.zip.part'
        with urllib.request.urlopen(profile['url'],timeout=60) as response,part.open('xb') as out:
            shutil.copyfileobj(response,out,1<<20)
        if sha(part)!=profile['zip_sha256']:raise ValueError('Downloaded archive SHA256 mismatch; retained .part for diagnosis')
        part.rename(archive)
    if sha(archive)!=profile['zip_sha256']:raise ValueError('Archive SHA256 mismatch')
    if not raw.exists():
        part=cache/'recovery.raw.part'
        digest=hashlib.sha256();written=0
        with zipfile.ZipFile(archive) as z:
            images=[i for i in z.infolist() if i.file_size==profile['raw_bytes'] and not i.is_dir()]
            if len(images)!=1:raise ValueError('Expected exactly one full recovery image member')
            with z.open(images[0]) as source,part.open('xb') as out:
                while chunk:=source.read(1<<20):
                    written+=len(chunk);digest.update(chunk)
                    if chunk.strip(b'\0'):out.write(chunk)
                    else:out.seek(len(chunk),1)
                out.truncate(written)
        if written!=profile['raw_bytes'] or digest.hexdigest()!=profile['raw_sha256']:
            raise ValueError('Extracted recovery size/SHA256 mismatch')
        part.rename(raw)
    if raw.stat().st_size!=profile['raw_bytes'] or sha(raw)!=profile['raw_sha256']:
        raise ValueError('Existing raw recovery size/SHA256 mismatch')
    return raw


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',type=pathlib.Path,required=True)
    p.add_argument('--cache',type=pathlib.Path,required=True)
    p.add_argument('--download',action='store_true')
    p.add_argument('--inspect-out',type=pathlib.Path)
    a=p.parse_args();profile=load_profile(a.profile)
    if a.inspect_out and (a.inspect_out.exists() or str(a.inspect_out.resolve()).startswith('/dev/')):
        p.error('Choose a NEW private inspection directory')
    raw=prepare(profile,a.cache,a.download)
    if a.inspect_out:
        subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('inspect_recovery.py')),str(raw),str(a.inspect_out)],check=True)
    print(json.dumps({'device':profile['device'],'build':profile['build'],'verified_raw':str(raw),'installed':False}))

if __name__=='__main__':main()
