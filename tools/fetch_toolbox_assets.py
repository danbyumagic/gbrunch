#!/usr/bin/env python3
"""Fetch pinned redistributable assets; never fetch a Google recovery image."""
import hashlib,json,pathlib,shutil,tarfile,tempfile,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
URL='https://github.com/danbyumagic/gbrunch/releases/download/v0.2-preview/gbrunch-compatibility-assets-v7.tar.gz'
SHA256='ba6eac2e2c1482bb3b0e4f4c1aee658b1dc488cce54e5ccbb2726e01fa3376c3'
def main():
 if (ROOT/'assets').exists():raise SystemExit('assets/ already exists; preserve it rather than overwrite.')
 with tempfile.TemporaryDirectory(prefix='gbrunch-assets-') as tmp:
  tmp=pathlib.Path(tmp);archive=tmp/'assets.tar.gz';h=hashlib.sha256()
  with urllib.request.urlopen(URL,timeout=60) as src,archive.open('wb') as out:
   while data:=src.read(1024*1024):out.write(data);h.update(data)
  if h.hexdigest()!=SHA256:raise SystemExit('Asset archive SHA256 mismatch; no assets installed.')
  with tarfile.open(archive,'r:gz') as tar:
   for member in tar.getmembers():
    if not (member.isfile() or member.isdir()):raise SystemExit('Unexpected archive link or special file.')
   tar.extractall(tmp/'unpacked',filter='data')
  package=tmp/'unpacked/gbrunch-compatibility-assets-v7'
  manifest=json.loads((package/'asset-hashes.json').read_text())
  for name,expected in manifest.items():
   path=package/name
   if not path.resolve().is_relative_to(package.resolve()):raise SystemExit('Invalid manifest path.')
   if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise SystemExit('Asset hash mismatch: '+name)
  shutil.copytree(package/'assets',ROOT/'assets')
  runtime=ROOT/'toolkit/runtime';runtime.mkdir(exist_ok=True)
  for name in ['internal-BOOTX64.EFI','trial-BOOTX64.EFI']:
   dest=runtime/name
   if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()!=manifest['runtime/'+name]:
    raise SystemExit('Existing loader differs; preserve it: '+str(dest))
   shutil.copy2(package/'runtime'/name,dest)
 print('Pinned GNU/AOSP/firmware assets installed. Google recovery remains a separate local download.')
if __name__=='__main__':main()
