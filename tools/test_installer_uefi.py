#!/usr/bin/env python3
"""Disposable OVMF/NVMe test: no physical disks or Google OS bytes."""
import pathlib,subprocess,os,gzip,stat,json,time,shutil,re
from prepare_native_android_gpu import entry
R=pathlib.Path(__file__).resolve().parents[1];B=R/'build/dualboot-installer';W=pathlib.Path('/tmp/gbrunch-installer-test');E=R/'evidence';env=os.environ.copy();env['LD_LIBRARY_PATH']=str(R/'tools/local/usr/lib/x86_64-linux-gnu')
for name in ['installed-target.raw','installed-plan.json','integration-result.json']:
 subprocess.run([str(R/'tools/local/usr/sbin/debugfs'),'-R',f'dump /{name} {W/name}',str(W/'work.ext4')],env=env,check=True,stdout=subprocess.DEVNULL)
(E/'installer-integration-result.json').write_bytes((W/'integration-result.json').read_bytes())
# Update the GNU-only diagnostic probe; no installed loader/GUIDs are changed.
layout=json.loads((W/'installed-plan.json').read_text());efi=next(p for p in layout['new_partitions'] if p['name']=='GBRUNCH_EFI')
image=str(W/'installed-target.raw')+'@@'+str(efi['offset'])
old=subprocess.check_output([str(R/'tools/local/usr/bin/mcopy'),'-i',image,'::/EFI/GBRUNCH/initrd.gz','-'],env=env)
probe=W/'probe-initrd.gz';probe.write_bytes(gzip.compress(gzip.decompress(old)+entry('installer/test_installed_layout.py',(R/'tools/test_installed_layout.py').read_bytes(),stat.S_IFREG|0o644,1300001)+entry('TRAILER!!!',b'',0,1300002),compresslevel=6,mtime=0))
subprocess.run([str(R/'tools/local/usr/bin/mcopy'),'-o','-i',image,str(probe),'::/EFI/GBRUNCH/initrd.gz'],env=env,check=True)
plan=json.loads((W/'installed-plan.json').read_text());ep=next(p for p in plan['new_partitions'] if p['name']=='GBRUNCH_EFI')['index']
# Register the same new ESP path using actual efibootmgr in virtual firmware.
init=(R/'tools/installer_init.sh').read_text().split("if grep -q 'gbrunch.fixture_tests=1'")[0]+f'''\nefibootmgr -v\nefibootmgr --create-only --disk /dev/nvme0n1 --part {ep} --label GBRUNCH --loader '\\EFI\\BOOT\\BOOTX64.EFI'\nefibootmgr -v\npython3 - <<'GUEST'\nimport subprocess,re\ns=subprocess.check_output(['efibootmgr','-v'],text=True)\nold=re.search(r'^BootOrder:\\s*(.*)$',s,re.M).group(1).strip()\nnew=re.search(r'^Boot([0-9A-Fa-f]{{4}})[ *].*GBRUNCH',s,re.M).group(1)\nsubprocess.run(['efibootmgr','--bootorder',old+','+new],check=True)\ns=subprocess.check_output(['efibootmgr','-v'],text=True)\nassert re.search(r'^BootOrder:\\s*(.*)$',s,re.M).group(1).strip()==old+','+new\nprint('INSTALLER_UEFI_APPEND_PASS',flush=True)\nGUEST\nsync\npoweroff -f\n'''
raw=gzip.decompress((B/'initrd.gz').read_bytes());ram=W/'register-initrd.gz';ram.write_bytes(gzip.compress(raw+entry('init',init.encode(),stat.S_IFREG|0o755,1200001)+entry('TRAILER!!!',b'',0,1200002),compresslevel=6,mtime=0))
q=R/'tools/qemu/usr/share';var=W/'OVMF_VARS.fd';shutil.copyfile(q/'OVMF/OVMF_VARS_4M.fd',var)
base=[str(R/'build/qemu11/qemu-system-x86_64'),'-L',str(q/'qemu'),'-machine','q35','-accel','tcg','-cpu','qemu64','-m','1536','-smp','2','-display','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-drive',f'if=pflash,format=raw,readonly=on,file={q}/OVMF/OVMF_CODE_4M.fd','-drive',f'if=pflash,format=raw,file={var}','-drive',f'if=none,id=target,format=raw,file={W}/installed-target.raw','-device','nvme,drive=target,serial=GBRUNCH_TEST_NVME']
def run(name,args,timeout=120):
 log=E/name
 with log.open('wb') as f:
  p=subprocess.Popen(base+args,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  try:p.wait(timeout=timeout)
  except subprocess.TimeoutExpired:p.terminate();p.wait();raise RuntimeError('Timeout '+str(log))
 text=log.read_text(errors='replace');print(text[-2000:]);return text
s=run('installer-uefi-registration.log',['-kernel',str(B/'linux-kernel'),'-initrd',str(ram),'-append','rdinit=/init console=ttyS0,115200 loglevel=4'])
assert 'INSTALLER_UEFI_APPEND_PASS' in s
s=run('installer-internal-uefi-boot.log',[])
assert 'INSTALLER_TARGET_BOOT_PASS:UEFI_GRUB_FRESH_GUIDS_COMPAT_V7' in s
(E/'installer-uefi-test.json').write_text(json.dumps(dict(passed=True,uefi_registration_preserves_prior_order=True,new_internal_esp_booted=True,fresh_guid_boot_argument_verified=True,compat_v7_sha_verified=True,scope='OVMF QEMU NVMe dummy source, GNU Linux probe, not Googlebook Android',physical_disks_accessed=False),indent=2)+'\n')
