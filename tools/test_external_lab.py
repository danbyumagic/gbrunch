#!/usr/bin/env python3
"""UEFI + USB3 Android research probe; regular files and disposable snapshots only."""
import json,os,pathlib,shutil,subprocess,time
root=pathlib.Path(__file__).resolve().parents[1]
q=root/'tools/qemu';b=root/'build';vars=b/'external-lab-OVMF_VARS.fd'
shutil.copyfile(q/'usr/share/OVMF/OVMF_VARS_4M.fd',vars)
cmd=[str(b/'qemu11/qemu-system-x86_64'),'-L',str(q/'usr/share/qemu'),
 '-machine','q35','-accel','tcg','-cpu','max','-m','4096','-smp','4',
 '-vga','none','-device',f'VGA,romfile={q}/usr/share/seabios/vgabios-stdvga.bin',
 '-display','none','-serial','stdio','-monitor','none','-net','none','-no-reboot',
 '-drive',f'if=pflash,format=raw,readonly=on,file={q}/usr/share/OVMF/OVMF_CODE_4M.fd',
 '-drive',f'if=pflash,format=raw,file={vars}',
 '-device','qemu-xhci,id=xhci',
 '-drive',f'if=none,id=usb,format=qcow2,snapshot=on,file={b}/external-lab.qcow2',
 '-device','usb-storage,bus=xhci.0,drive=usb,removable=on']
log=root/'evidence/external-lab-uefi-usb.log';start=time.monotonic()
with log.open('wb') as f:
 p=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 try:code=p.wait(timeout=100);timeout=False
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
(root/'evidence/external-lab-uefi-usb.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
assert result['original_kernel_started'] and result['init_reached'] and not result['kernel_panic'],result
