#!/usr/bin/env python3
"""Add only three unmodified firmware files to the independently owned V6 image."""
import hashlib,json,pathlib,shutil,subprocess,os,tarfile,urllib.request
R=pathlib.Path(__file__).resolve().parents[1];D=R/'downloads/hp-radio-firmware';B=R/'build/compat-wifi-v7';B.mkdir(exist_ok=True)
commit='788aadc8f73d93908cf8545b2fc770fb6580a3f2'
url=f'https://gitlab.com/kernel-firmware/linux-firmware/-/raw/{commit}/iwlwifi-ma-b0-gf-a0.pnvm'
pnvm=urllib.request.urlopen(url,timeout=45).read();assert hashlib.sha256(pnvm).hexdigest()=='3b4f516cd03e402ff814446c3dec83067071a8995b8541cba6d7a1f8fd4c9bbf';(D/'iwlwifi-ma-b0-gf-a0.pnvm').write_bytes(pnvm)
regurl='https://www.kernel.org/pub/software/network/wireless-regdb/wireless-regdb-2026.09.03.tar.xz'
archive=urllib.request.urlopen(regurl,timeout=45).read();assert hashlib.sha256(archive).hexdigest()=='b22e0901227b820cd1c280abe681a15b773a5103a5e10dc442e94ebb34cbf58d'
(D/'wireless-regdb-2026.09.03.tar.xz').write_bytes(archive)
with tarfile.open(D/'wireless-regdb-2026.09.03.tar.xz') as t:
 for name in ['regulatory.db','regulatory.db.p7s','LICENSE','wens.x509.pem']:
  data=t.extractfile('wireless-regdb-2026.09.03/'+name).read();(D/('REGDB-LICENSE' if name=='LICENSE' else name)).write_bytes(data)
e=os.environ.copy();e['LD_LIBRARY_PATH']=str(R/'tools/local/usr/lib/x86_64-linux-gnu')
subprocess.run(['openssl','cms','-verify','-binary','-inform','DER','-in',str(D/'regulatory.db.p7s'),'-content',str(D/'regulatory.db'),'-certfile',str(D/'wens.x509.pem'),'-noverify','-out','/dev/null'],check=True)
base=R/'build/compat-radio-v6/compat.ext4';out=B/'compat.ext4';shutil.copyfile(base,out)
commands=[];files=[]
for name in ['iwlwifi-ma-b0-gf-a0.pnvm','regulatory.db','regulatory.db.p7s']:
 p=D/name;dest='/firmware/'+name
 commands += [f'write {p} {dest}',f'ea_set {dest} security.selinux u:object_r:vendor_firmware_file:s0',f'set_inode_field {dest} uid 0',f'set_inode_field {dest} gid 0',f'set_inode_field {dest} mode 0100644']
 files.append(dict(name=name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source=url if name.endswith('.pnvm') else regurl))
cmd=B/'firmware.commands';cmd.write_text('\n'.join(commands)+'\n')
with (B/'debugfs.txt').open('w') as log:subprocess.run([str(R/'tools/local/usr/sbin/debugfs'),'-w','-f',str(cmd),str(out)],env=e,stdout=log,stderr=subprocess.STDOUT,check=True)
subprocess.run([str(R/'tools/local/usr/sbin/e2fsck'),'-fn',str(out)],env=e,check=True)
manifest=dict(base_v6_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),v7_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),files=files,regdb_archive_sha256=hashlib.sha256(archive).hexdigest(),regdb_detached_signature_verified=True,google_images_modified=False,graphics_configuration_modified=False,hp_tested=False)
(B/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
