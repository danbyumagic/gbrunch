#!/usr/bin/env python3
"""Stage original Ruby Xe dependency closure and pinned Meteor Lake firmware.
No module loading on the host; no recovery image writes or proprietary OS package.
"""
import hashlib,json,lzma,pathlib,shutil,subprocess,urllib.request
R=pathlib.Path(__file__).resolve().parents[1];O=R/'build/xe-probe';O.mkdir(exist_ok=True)
rows=json.loads((R/'evidence/module-inventory.json').read_text());mods={}
for m in rows:
 if m['file'].startswith(('system_dlkm_a-files/','vendor_dlkm_a-files/')):
  n=pathlib.Path(m['file']).stem.replace('-','_');mods[n]=m
selected={};order=[]
def select(n):
 n=n.replace('-','_')
 if n in selected:return
 if n not in mods:raise ValueError('Missing original dependency '+n)
 m=mods[n];assert m['elf_machine']==62;selected[n]=m
 deps=next((x[8:] for x in m['modinfo'] if x.startswith('depends=')),'')
 for dep in deps.split(','):
  if dep:select(dep)
 order.append(n)
select('xe')
core=json.loads((R/'evidence/kernel-symbol-crcs.json').read_text());staged=O/'modules';staged.mkdir(exist_ok=True)
manifest=[]
for n in order:
 m=selected[n];source=R/'extracted/ruby'/m['file'];dest=staged/source.name
 for name,crc in m['symbol_crcs'].items():
  if name in core:assert int(crc,16)==int(core[name],16),(n,name)
 shutil.copyfile(source,dest)
 manifest.append({'name':n,'file':dest.name,'source':m['file'],'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'signed':m['signed'],'vermagic':next(x for x in m['modinfo'] if x.startswith('vermagic=')),'core_import_crc_check':'pass'})
(O/'module-load-order').write_text('\n'.join(x['file'] for x in manifest)+'\n')
pkg=json.loads((R/'evidence/xe-firmware-package.json').read_text());deb=R/'tools/debs'/pathlib.Path(pkg['Filename']).name
if not deb.exists():urllib.request.urlretrieve('https://deb.debian.org/debian/'+pkg['Filename'],deb)
assert hashlib.sha256(deb.read_bytes()).hexdigest()==pkg['SHA256']
private=R/'tools/xe-firmware';subprocess.run(['dpkg-deb','-x',str(deb),str(private)],check=True)
fw=private/'usr/lib/firmware';output=O/'firmware/i915';output.mkdir(parents=True,exist_ok=True);firmware=[]
for name in ['mtl_guc_70.bin','mtl_huc_gsc.bin','mtl_gsc_1.bin','mtl_dmc.bin']:
 source=fw/'i915'/name
 if not source.exists():source=fw/'i915'/(name+'.xz')
 assert source.exists(),name
 data=source.read_bytes()
 if data.startswith(bytes.fromhex('fd377a585a00')):data=lzma.decompress(data)
 (output/name).write_bytes(data);firmware.append({'name':'i915/'+name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'package':pkg['Version']})
(O/'manifest.json').write_text(json.dumps({'scope':'original-kernel Xe module/firmware staging; physical Xe and Android graphics not established','target_gpu':'8086:7d45','modules':manifest,'firmware':firmware,'signature_force':'No force-loading or signature bypass','original_recovery':'unchanged'},indent=2)+'\n')
print(json.dumps({'modules':len(manifest),'firmware_files':len(firmware),'bytes':sum((staged/x['file']).stat().st_size for x in manifest)+sum(x['bytes'] for x in firmware)},indent=2))
