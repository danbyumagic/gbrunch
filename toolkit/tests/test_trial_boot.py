#!/usr/bin/env python3
"""Actual ISO-on-64GB-USB boot, virtual Ethernet, screenshots; no physical disks."""
import pathlib,subprocess,shutil,socket,json,time,os,sys
R=pathlib.Path(__file__).resolve().parents[2];W=pathlib.Path('/tmp/gbrunch-toolbox-test');E=R/'evidence';q=R/'tools/qemu/usr/share';ISO=pathlib.Path('/dev/shm/gbrunch-toolbox-output/gbrunch-toolbox-v0.2-amd64.iso')
firmware='uefi';usb=W/'usb-uefi.qcow2'
sock=W/('qmp-trial.sock');sock.unlink(missing_ok=True)
cmd=[str(R/'tools/qemu/usr/bin/qemu-system-x86_64'),'-L',str(q/'qemu'),'-machine','q35','-accel','tcg','-cpu','max','-m','1536','-smp','2','-display','none','-vga','none','-device',f'VGA,romfile={q}/seabios/vgabios-stdvga.bin','-serial','file:'+str(E/('toolbox-trial-boot.log')),'-monitor','none','-qmp',f'unix:{sock},server=on,wait=off','-no-reboot','-netdev','user,id=net0','-device','e1000,netdev=net0','-device','qemu-xhci,id=xhci','-drive',f'if=none,id=usb,format=qcow2,file={usb},detect-zeroes=unmap,discard=unmap','-device','usb-storage,drive=usb,bootindex=1']
if firmware=='uefi':
 var=W/'TRIAL_VARS.fd';shutil.copyfile(q/'OVMF/OVMF_VARS_4M.fd',var);cmd+=['-drive',f'if=pflash,format=raw,readonly=on,file={q}/OVMF/OVMF_CODE_4M.fd','-drive',f'if=pflash,format=raw,file={var}']
else:cmd+=['-bios',str(q/'seabios/bios-256k.bin')]
env=os.environ.copy();env['LD_LIBRARY_PATH']=str(R/'tools/qemu/usr/lib/x86_64-linux-gnu')+':'+str(R/'tools/local/usr/lib/x86_64-linux-gnu');env['QEMU_MODULE_DIR']=str(R/'tools/qemu/usr/lib/x86_64-linux-gnu/qemu')
p=subprocess.Popen(cmd,env=env,stdout=subprocess.DEVNULL,stderr=(E/('toolbox-trial-qemu.log')).open('wb'))
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
 time.sleep(4);call('stop');call('screendump',dict(filename=str(W/'trial-menu.ppm')));f.close();s.close();print('TRIAL_VM_PAUSED',flush=True)
 log=E/'toolbox-trial-boot.log';deadline=time.monotonic()+240
 while time.monotonic()<deadline:
  if 'Linux version 6.18.21' in log.read_text(errors='replace'):break
  if p.poll() is not None:raise RuntimeError('VM exited before kernel handoff')
  time.sleep(1)
 else:raise RuntimeError('No original Google kernel handoff')
 (E/'toolbox-trial-boot-test.json').write_text(json.dumps(dict(passed=True,uefi_toolbox_menu_to_trial=True,original_google_kernel_handoff=True,scope='QEMU dummy system payloads; fixture GRUB timeout/loglevel adjusted for observation; Android desktop not tested'),indent=2)+'\n')
 print('TRIAL_GOOGLE_KERNEL_HANDOFF_PASS',flush=True);p.terminate();p.wait(timeout=20)
except Exception:
 p.terminate();p.wait();raise
