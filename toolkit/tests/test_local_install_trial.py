#!/usr/bin/env python3
"""Actual live ISO filesystem + 64GB USB, setup confirmation and reboot persistence."""
import pathlib,subprocess,os,socket,time,re,json,shlex,hashlib
R=pathlib.Path(__file__).resolve().parents[2];W=pathlib.Path('/tmp/gbrunch-toolbox-test');E=R/'evidence';q=R/'tools/qemu/usr/share';usb=W/'usb-uefi.qcow2';iso=pathlib.Path('/dev/shm/gbrunch-toolbox-output/gbrunch-toolbox-v0.2-amd64.iso')
env=os.environ.copy();env['LD_LIBRARY_PATH']=str(R/'tools/qemu/usr/lib/x86_64-linux-gnu')+':'+str(R/'tools/local/usr/lib/x86_64-linux-gnu');env['QEMU_MODULE_DIR']=str(R/'tools/qemu/usr/lib/x86_64-linux-gnu/qemu')
class Guest:
 def __init__(self,n):
  sock=W/('serial-'+str(n)+'.sock');sock.unlink(missing_ok=True);self.log=(E/('toolbox-local-'+str(n)+'.log')).open('wb');self.data=''
  cmd=[str(R/'tools/qemu/usr/bin/qemu-system-x86_64'),'-L',str(q/'qemu'),'-drive',f'if=pflash,format=raw,readonly=on,file={q}/OVMF/OVMF_CODE_4M.fd','-drive',f'if=pflash,format=raw,file={W}/LOCAL_VARS.fd','-machine','q35','-accel','tcg','-cpu','qemu64','-m','1536','-smp','2','-display','none','-vga','none','-device',f'VGA,romfile={q}/seabios/vgabios-stdvga.bin','-monitor','none','-serial',f'unix:{sock},server=on,wait=off','-no-reboot','-netdev','user,id=net0','-device','e1000,netdev=net0','-device','qemu-xhci,id=xhci','-drive',f'if=none,id=usb,format=qcow2,file={usb},detect-zeroes=unmap,discard=unmap','-device','usb-storage,drive=usb','-drive',f'if=none,id=target,format=qcow2,file=/tmp/gbrunch-toolbox-v2-fixtures/windows.qcow2,detect-zeroes=unmap,discard=unmap','-device','nvme,drive=target,serial=GBRUNCH_TOOLBOX_TEST','-virtfs','local,path=/tmp/gbrunch-toolbox-v2-fixtures,mount_tag=fixtures,security_model=mapped-xattr','-virtfs',f'local,path={R},mount_tag=repo,security_model=none,readonly=on','-kernel',str(W/'linux-kernel'),'-initrd',str(W/'initrd.img'),'-append','boot=live components username=live hostname=gbrunch-toolbox persistence persistence-label=GBWORK locales=en_US.UTF-8 keyboard-layouts=us console=tty0 console=ttyS0,115200 loglevel=4 systemd.unit=multi-user.target']
  self.p=subprocess.Popen(cmd,env=env,stdout=subprocess.DEVNULL,stderr=(E/('toolbox-local-qemu-'+str(n)+'.log')).open('wb'))
  for _ in range(100):
   if sock.exists():break
   time.sleep(.1)
  self.s=socket.socket(socket.AF_UNIX);self.s.connect(str(sock));self.s.settimeout(1)
 def wait(self,pattern,timeout=240):
  regex=re.compile(pattern);end=time.monotonic()+timeout
  while time.monotonic()<end:
   match=regex.search(self.data)
   if match:self.data=self.data[match.end():];return match
   try:b=self.s.recv(65536)
   except socket.timeout:continue
   if not b:raise RuntimeError('Guest serial closed waiting for '+pattern)
   self.log.write(b);self.log.flush();self.data+=b.decode(errors='replace')
  raise TimeoutError('Waiting for '+pattern+'; tail='+self.data[-2000:])
 def send(self,s):time.sleep(.2);self.s.sendall((s+'\n').encode())
 def login(self):
  self.wait(r'login:');self.send('live');self.wait(r'Password:');self.send('live');self.wait(r'live@[^: ]+:.*\$');self.send('stty -echo');self.wait(r'live@[^: ]+:.*\$')
 def python(self,code,marker):
  self.send('python3 -c '+shlex.quote(code));return self.wait(marker)
 def shutdown(self):
  self.send('sudo poweroff');end=time.monotonic()+180
  while self.p.poll() is None and time.monotonic()<end:
   try:
    b=self.s.recv(65536)
    if b:self.log.write(b);self.log.flush()
    else:break
   except socket.timeout:pass
  self.p.wait(timeout=20);self.s.close();self.log.close()
 def abort(self):
  if self.p.poll() is None:self.p.terminate();self.p.wait()

import shutil
F=pathlib.Path('/tmp/gbrunch-toolbox-v2-fixtures')
shutil.copyfile(q/'OVMF/OVMF_VARS_4M.fd',W/'LOCAL_VARS.fd')
subprocess.run([str(R/'build/qemu11/qemu-img'),'rebase','-u','-f','qcow2','-F','raw','-b',str(iso),str(usb)],check=True)
subprocess.run([str(R/'build/qemu11/qemu-img'),'create','-f','qcow2','-F','raw','-b',str(F/'windows.raw'),str(F/'windows.qcow2')],check=True)
g=Guest(1)
try:
 g.login();g.send('sudo mkdir -p /mnt/repo /mnt/fixtures; sudo mount -t 9p -o trans=virtio,version=9p2000.L repo /mnt/repo; sudo mount -t 9p -o trans=virtio,version=9p2000.L fixtures /mnt/fixtures; echo TEST_MOUNTS_READY');g.wait('TEST_MOUNTS_READY');g.wait(r'live@[^: ]+:.*\$')
 g.send('sudo python3 -u /mnt/repo/toolkit/tests/test_local_install_guest.py');g.wait('TOOLBOX_LOCAL_INSTALL_TRIAL_PASS',timeout=900);g.wait(r'live@[^: ]+:.*\$');g.shutdown()
 result=json.loads((F/'result.json').read_text());(E/'toolbox-local-install-trial-test.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
except Exception:
 g.abort();raise
