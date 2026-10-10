#!/usr/bin/env python3
"""UEFI + USB3 Android research probe; regular files and disposable snapshots only."""
import argparse,json,os,pathlib,shutil,subprocess,time
from read_native_android_logs import read_logs
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--seconds',type=int,default=140)
parser.add_argument('--image',type=pathlib.Path)
parser.add_argument('--image-manifest',type=pathlib.Path)
parser.add_argument('--hp-smbios',action='store_true')
parser.add_argument('--label',default='native-android-uefi-usb')
args=parser.parse_args()
assert 60<=args.seconds<=300
root=pathlib.Path(__file__).resolve().parents[1]
q=root/'tools/qemu';b=root/'build';vars=b/'native-android-gpu/native-OVMF_VARS.fd'
assert all(x.isalnum() or x in '-_' for x in args.label)
snapshot=b/'native-android-gpu'/(args.label+'-snapshot.qcow2')
assert not snapshot.exists()
image=args.image.resolve() if args.image else b/'native-android-gpu/uefi-usb-view.qcow2'
subprocess.run([str(b/'qemu11/qemu-img'),'create','-f','qcow2','-F','qcow2','-b',str(image),str(snapshot)],check=True)
shutil.copyfile(q/'usr/share/OVMF/OVMF_VARS_4M.fd',vars)
cmd=[str(b/'qemu11/qemu-system-x86_64'),'-L',str(q/'usr/share/qemu'),
 '-machine','q35','-accel','tcg','-cpu','max','-m','4096','-smp','4',
 '-vga','none','-device',f'VGA,romfile={q}/usr/share/seabios/vgabios-stdvga.bin',
 '-display','none','-serial','stdio','-monitor','none','-net','none','-no-reboot',
 '-drive',f'if=pflash,format=raw,readonly=on,file={q}/usr/share/OVMF/OVMF_CODE_4M.fd',
 '-drive',f'if=pflash,format=raw,file={vars}',
 '-device','qemu-xhci,id=xhci',
 '-drive',f'if=none,id=usb,format=qcow2,file={snapshot}',
 '-device','usb-storage,bus=xhci.0,drive=usb,removable=on']
if args.hp_smbios:cmd+=['-smbios','type=1,manufacturer=HP,product=HP Envy x360 2-in-1 Laptop 15-fe1xxx','-smbios','type=2,manufacturer=HP,product=8C4F']
log=root/'evidence'/(args.label+'.log');start=time.monotonic()
with log.open('wb') as f:
 p=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 try:code=p.wait(timeout=args.seconds);timeout=False
 except subprocess.TimeoutExpired:
  p.terminate();code=p.wait(timeout=10);timeout=True
s=log.read_text(errors='replace')
result={'scope':'QEMU UEFI USB3 boot, no host devices or network; no stable desktop claim',
 'command':cmd,'seconds':round(time.monotonic()-start,2),'exit_code':code,'timeout':timeout,
 'original_kernel_started':'Linux version 6.18.21' in s,
 'first_stage_init':'init first stage started' in s,
 'compat_loaded':'independent compatibility init loaded' in s,
 'second_stage_init':'init second stage started' in s,
 'kernel_panic':'Kernel panic' in s,
 'init_reached':('init first stage started' in s or 'init second stage started' in s)}
(root/'evidence'/(args.label+'.json')).write_text(json.dumps(result,indent=2)+'\n')
result['xe_first_stage_loaded']='Loaded kernel module /lib/modules/xe.ko' in s
result['persistent_logger_started']="started service 'gbrunch.persistlogs' has pid" in s
(root/'evidence'/(args.label+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
assert result['original_kernel_started'] and result['init_reached'] and not result['kernel_panic'],result

assert result['xe_first_stage_loaded'] and result['compat_loaded'] and result['persistent_logger_started'],result
partition=None
if args.image_manifest:
    partition=next(x for x in json.loads(args.image_manifest.read_text())['appended_partitions'] if x['name']=='GBLOG')
files=read_logs(snapshot,partition,'native-android' if args.label=='native-android-uefi-usb' else args.label)
result['fat_log_files']=files
required=['logcat.txt','modules.txt','properties.txt']
if 'status.txt' in files:required+=['status.txt']
else:required+=['drm-nodes.txt']
result['fat_logs_recovered']=all(files[k]['present'] and (files[k]['bytes'] or k=='drm-nodes.txt') for k in required)
(root/'evidence'/(args.label+'.json')).write_text(json.dumps(result,indent=2)+'\n')
assert result['fat_logs_recovered'], 'Logger launch is insufficient: FAT files must actually be recovered.'
