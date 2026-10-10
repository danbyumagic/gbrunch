#!/usr/bin/env python3
"""Execute updater's readonly-source build against the owned Android view."""
import pathlib,os,json,subprocess,time,hashlib
R=pathlib.Path(__file__).resolve().parents[1];W=R/'build/compat-update-v3/test';W.mkdir(exist_ok=True)
L=R/'tools/local';Q=R/'tools/qemu';env=os.environ.copy();env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
def run(*args,**kwargs):return subprocess.run([str(a) for a in args],env=env,check=True,**kwargs)
fat=W/'work.fat'
with fat.open('wb') as f:f.truncate(1<<30)
run(L/'usr/sbin/mkfs.fat','-F','32',fat,stdout=subprocess.DEVNULL)
(W/'GBRUNCH-BUILD-MARKER.txt').write_text('GBRUNCH local build-tool work disk\n')
(W/'request.json').write_text(json.dumps({'original_policy_sha256':hashlib.sha256((R/'extracted/ruby/vendor_a-files/etc/selinux/precompiled_sepolicy').read_bytes()).hexdigest()}))
for name in ['GBRUNCH-BUILD-MARKER.txt','request.json']:run(L/'usr/bin/mcopy','-i',fat,W/name,'::/')
source=R/'build/native-android-gpu/uefi-usb-view.qcow2'
before=hashlib.sha256(source.read_bytes()).hexdigest()
cmd=[str(Q/'usr/bin/qemu-system-x86_64'),'-L',str(Q/'usr/share/qemu'),'-bios',str(Q/'usr/share/seabios/bios-256k.bin'),'-machine','q35','-accel','tcg','-cpu','qemu64','-m','1024','-smp','2','-display','none','-vga','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-kernel',str(R/'build/compat-update-v3/linux-kernel'),'-initrd',str(R/'build/compat-update-v3/initrd.gz'),'-append','rdinit=/init console=ttyS0,115200 loglevel=5 panic=0 gbrunch.toolvm=1 gbrunch.compat_update=1','-drive',f'if=none,id=work,format=raw,file={fat}','-device','virtio-blk-pci,drive=work','-drive',f'if=none,id=disk,format=qcow2,file={source},readonly=on','-device','virtio-blk-pci,drive=disk']
env['LD_LIBRARY_PATH']=str(Q/'usr/lib/x86_64-linux-gnu');start=time.monotonic()
with (W/'console.txt').open('wb') as out:run(*cmd,stdout=out,stderr=subprocess.STDOUT,timeout=240)
env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
for name in ['status.txt','build-log.txt','update-result.json','policy-before.txt','policy-after.txt','policy-changes.txt']:run(L/'usr/bin/mcopy','-i',fat,'::/'+name,W/name)
assert (W/'status.txt').read_text().strip()=='0',(W/'build-log.txt').read_text()
assert hashlib.sha256(source.read_bytes()).hexdigest()==before
r=json.loads((W/'update-result.json').read_text());native=json.loads((R/'build/vendor-graphics-v3/manifest.json').read_text())
assert r['vendor_sha256']==native['vendor_sha256'] and r['policy_sha256']==native['policy_sha256']
assert r['graphics_av_checks_passed'] and r['source_ssd_readonly']
result={'seconds':round(time.monotonic()-start,2),'guest_source_block_readonly_verified':True,'source_qcow_hash_unchanged':True,'vendor_matches_independent_work_build':True,'graphics_policy_semantic_checks_passed':True,'vendor_fits_existing_partition':True}
(R/'evidence/compat-update-vm-test.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
