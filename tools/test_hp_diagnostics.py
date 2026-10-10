#!/usr/bin/env python3
"""Test EFI USB boot/log persistence using only disposable regular disk files."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,time,re
from inspect_recovery import gpt
ROOT=pathlib.Path(__file__).resolve().parents[1];B=ROOT/'build/hp-diagnostics';L=ROOT/'tools/local';Q=ROOT/'tools/qemu'
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['linux','google','batch'],required=True);p.add_argument('--reject-marker',action='store_true');a=p.parse_args()
name='hp-'+a.mode+'-usb'+('-reject-marker' if a.reject_marker else '')
with (B/'gbrunch-hp-diagnostics.img').open('rb') as f:parts=gpt(f)
assert len(parts)==1 and parts[0]['name']=='GBRUNCH-HP-ESP'
test=B/(name+'.img');shutil.copyfile(B/'gbrunch-hp-diagnostics.img',test)
env=os.environ.copy();env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
cfg=(B/'grub.cfg').read_text().replace('set timeout=12','set timeout=1')
cfg=re.sub(r'set default=\d+', 'set default='+('0' if a.mode=='batch' else '3' if a.mode=='linux' else '4'), cfg)
if a.mode=='batch':cfg=cfg.replace('gbrunch.batch=1\n','gbrunch.batch=1 gbrunch.unattended=1\n')
path=B/(name+'-grub.cfg');path.write_text(cfg)
fat=str(test)+'@@1048576'
subprocess.run([str(L/'usr/bin/mcopy'),'-o','-i',fat,str(path),'::/EFI/GBRUNCH/grub.cfg'],env=env,check=True)
if a.reject_marker:
 bad=B/'invalid-marker.txt';bad.write_text('NOT THE OWNED DIAGNOSTIC MEDIA\n')
 subprocess.run([str(L/'usr/bin/mcopy'),'-o','-i',fat,str(bad),'::/GBRUNCH-MEDIA.TXT'],env=env,check=True)
decoy=B/'internal-decoy.raw'
if not decoy.exists():
 with decoy.open('wb') as f:f.write(b'GBRUNCH_OWNED_TEST_DECOY\n');f.truncate(8*1024*1024)
before=hashlib.sha256(decoy.read_bytes()).hexdigest()
vars=B/(name+'-OVMF_VARS.fd');shutil.copyfile(Q/'usr/share/OVMF/OVMF_VARS_4M.fd',vars)
env['LD_LIBRARY_PATH']=str(Q/'usr/lib/x86_64-linux-gnu')
cmd=[str(Q/'usr/bin/qemu-system-x86_64'),'-L',str(Q/'usr/share/qemu'),'-machine','q35','-accel','tcg','-cpu','max','-m','1536','-smp','2','-vga','none','-device',f'VGA,romfile={Q}/usr/share/seabios/vgabios-stdvga.bin','-display','none','-serial','stdio','-monitor','none','-net','none','-no-reboot',
 '-drive',f'if=pflash,format=raw,readonly=on,file={Q}/usr/share/OVMF/OVMF_CODE_4M.fd',
 '-drive',f'if=pflash,format=raw,file={vars}',
 '-device','qemu-xhci,id=xhci','-drive',f'if=none,id=usb,format=raw,file={test}',
 '-device','usb-storage,bus=xhci.0,drive=usb,removable=on',
 '-drive',f'if=none,id=internal,format=raw,readonly=on,file={decoy}',
 '-device','nvme,drive=internal,serial=GBRUNCHTESTINTERNAL']
log=ROOT/'evidence'/(name+'.log');start=time.monotonic()
with log.open('wb') as out:
 proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,env=env)
 try:code=proc.wait(timeout=300 if a.mode=='batch' else 100);timed=False
 except subprocess.TimeoutExpired:proc.terminate();code=proc.wait(timeout=5);timed=True
text=log.read_text(errors='replace')
env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
listing=subprocess.run([str(L/'usr/bin/mdir'),'-b','-s','-i',fat,'::/GBRUNCH-LOGS'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
saved=listing.stdout
(ROOT/'evidence'/(name+'-fat-logs.txt')).write_text(saved)
mode='linux' if a.mode=='batch' else a.mode
result={'name':name,'command':cmd,'duration':round(time.monotonic()-start,2),'exit_code':code,'timeout':timed,'efi_usb_boot':('GBRUNCH_HP_DIAGNOSTICS_STARTED mode='+mode) in text,'completed':('GBRUNCH_HP_DIAGNOSTICS_COMPLETE mode='+mode) in text,'log_saved':'GBRUNCH_LOGS_SAVED' in text,'fat_complete_marker':'COMPLETE.txt' in saved,'unrelated_disk_unchanged':before==hashlib.sha256(decoy.read_bytes()).hexdigest(),'marker_rejected':'GBRUNCH_LOG_STORAGE_REFUSED matching_media=0' in text,'gpt_crc':'pass','scope':'Disposable disk file on emulated USB3; no HP or host physical disk access'}
if a.mode=='batch':
 result.update({'full_batch_saved':'test-summary.txt' in saved,'automatic_google_kernel_started':'GBRUNCH_HP_DIAGNOSTICS_STARTED mode=google' in text,'google_kernel_completed':'GBRUNCH_HP_DIAGNOSTICS_COMPLETE mode=google' in text,'kexec_result_saved':'kexec.txt' in saved})
(ROOT/'evidence'/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
assert result['efi_usb_boot'] and result['completed'] and result['unrelated_disk_unchanged'] and not timed and code==0,result
if a.reject_marker:assert result['marker_rejected'] and not result['log_saved'] and not result['fat_complete_marker'],result
else:assert result['log_saved'] and result['fat_complete_marker'],result
if a.mode=='batch':assert result['full_batch_saved'] and result['automatic_google_kernel_started'] and result['google_kernel_completed'],result
