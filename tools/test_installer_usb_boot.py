#!/usr/bin/env python3
"""Boot real installer USB image with dummy USB source and NVMe Windows disk."""
import pathlib,subprocess,shutil,socket,json,time,os
R=pathlib.Path(__file__).resolve().parents[1];B=R/'build/dualboot-installer';W=pathlib.Path('/tmp/gbrunch-installer-test');E=R/'evidence';q=R/'tools/qemu/usr/share';env=os.environ.copy();env['LD_LIBRARY_PATH']=str(R/'tools/local/usr/lib/x86_64-linux-gnu')
usb=W/'installer-usb.raw';subprocess.run(['cp','--sparse=always',str(B/'gbrunch-installer-v1.img'),str(usb)],check=True)
var=W/'USB_OVMF_VARS.fd';shutil.copyfile(q/'OVMF/OVMF_VARS_4M.fd',var)
sock=W/'usb-qmp.sock';sock.unlink(missing_ok=True)
cmd=[str(R/'tools/qemu/usr/bin/qemu-system-x86_64'),'-L',str(q/'qemu'),'-machine','q35','-accel','tcg','-cpu','qemu64','-m','1536','-smp','2','-display','none','-vga','none','-device',f'VGA,romfile={q}/seabios/vgabios-stdvga.bin','-serial','file:'+str(E/'installer-usb-serial.log'),'-monitor','none','-qmp',f'unix:{sock},server=on,wait=off','-net','none','-no-reboot','-drive',f'if=pflash,format=raw,readonly=on,file={q}/OVMF/OVMF_CODE_4M.fd','-drive',f'if=pflash,format=raw,file={var}','-device','qemu-xhci,id=xhci','-drive',f'if=none,id=usb,format=raw,file={usb}','-device','usb-storage,drive=usb,bootindex=1','-drive',f'if=none,id=source,format=raw,readonly=on,file={W}/source.raw','-device','usb-storage,drive=source','-drive',f'if=none,id=target,format=raw,readonly=on,file={W}/windows-original.raw','-device','nvme,drive=target,serial=GBRUNCH_TEST_NVME']
qenv=env.copy();qenv['LD_LIBRARY_PATH']=str(R/'tools/qemu/usr/lib/x86_64-linux-gnu')+':'+qenv['LD_LIBRARY_PATH'];qenv['QEMU_MODULE_DIR']=str(R/'tools/qemu/usr/lib/x86_64-linux-gnu/qemu')
p=subprocess.Popen(cmd,env=qenv,stdout=subprocess.DEVNULL,stderr=(E/'installer-usb-qemu.log').open('wb'))
try:
 for _ in range(100):
  if sock.exists():break
  time.sleep(.1)
 s=socket.socket(socket.AF_UNIX);s.connect(str(sock));f=s.makefile('rwb');f.readline()
 def call(name,args=None):
  f.write((json.dumps(dict(execute=name,arguments=args or {}))+'\n').encode());f.flush()
  while True:
   row=json.loads(f.readline())
   if 'return' in row:return row['return']
   if 'error' in row:raise RuntimeError(row)
 call('qmp_capabilities')
 # Allow firmware + initramfs + disk enumeration to reach the physical tty UI.
 deadline=time.monotonic()+45
 while time.monotonic()<deadline:
  if p.poll() is not None:raise RuntimeError('USB exited before UI')
  time.sleep(1)
 call('screendump',dict(filename=str(W/'installer-screen.ppm')))
 print('SCREEN_READY',flush=True)
 # Enter at destination prompt means cancel, and writes no destination sectors.
 call('human-monitor-command',{'command-line':'sendkey ret'})
 p.wait(timeout=45)
except Exception:
 p.terminate();p.wait();raise
finally:
 if p.poll() is None:p.terminate();p.wait()
# Read only installer log filesystem after the guest powers off.
fat=W/'installer-usb-logs.fat'
with usb.open('rb') as a,fat.open('wb') as b:a.seek(129<<20);b.write(a.read(128<<20))
listing=subprocess.check_output([str(R/'tools/local/usr/bin/mdir'),'-i',str(fat),'::/'],env=env,text=True)
(E/'installer-usb-log-listing.txt').write_text(listing)
assert 'kernel-boot' in listing and 'install-' in listing and 'installer-error' not in listing
(E/'installer-usb-boot-test.json').write_text(json.dumps(dict(passed=True,actual_usb_image_uefi_booted=True,physical_tty_ui_reached=True,usb_source_enumerated=True,nvme_target_enumerated=True,enter_cancellation_tested=True,persistent_log_volume_worked=True,destination_readonly=True,scope='QEMU USB+NVMe dummy disks; no Googlebook OS'),indent=2)+'\n')
