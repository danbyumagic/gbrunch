#!/usr/bin/env python3
"""Actual live ISO filesystem + 64GB USB, setup confirmation and reboot persistence."""
import pathlib,subprocess,os,socket,time,re,json,shlex,hashlib
R=pathlib.Path(__file__).resolve().parents[2];W=pathlib.Path('/tmp/gbrunch-toolbox-test');E=R/'evidence';q=R/'tools/qemu/usr/share';usb=W/'usb-uefi.qcow2';iso=pathlib.Path('/dev/shm/gbrunch-toolbox-output/gbrunch-toolbox-v0.2-amd64.iso')
env=os.environ.copy();env['LD_LIBRARY_PATH']=str(R/'tools/qemu/usr/lib/x86_64-linux-gnu')+':'+str(R/'tools/local/usr/lib/x86_64-linux-gnu');env['QEMU_MODULE_DIR']=str(R/'tools/qemu/usr/lib/x86_64-linux-gnu/qemu')
class Guest:
 def __init__(self,n):
  sock=W/('serial-'+str(n)+'.sock');sock.unlink(missing_ok=True);self.log=(E/('toolbox-persistence-'+str(n)+'.log')).open('wb');self.data=''
  cmd=[str(R/'tools/qemu/usr/bin/qemu-system-x86_64'),'-L',str(q/'qemu'),'-bios',str(q/'seabios/bios-256k.bin'),'-machine','q35','-accel','tcg','-cpu','qemu64','-m','1536','-smp','2','-display','none','-vga','none','-device',f'VGA,romfile={q}/seabios/vgabios-stdvga.bin','-monitor','none','-serial',f'unix:{sock},server=on,wait=off','-no-reboot','-netdev','user,id=net0','-device','e1000,netdev=net0','-device','qemu-xhci,id=xhci','-drive',f'if=none,id=usb,format=qcow2,file={usb},detect-zeroes=unmap,discard=unmap','-device','usb-storage,drive=usb','-kernel',str(W/'linux-kernel'),'-initrd',str(W/'initrd.img'),'-append','boot=live components username=live hostname=gbrunch-toolbox persistence persistence-label=GBWORK locales=en_US.UTF-8 keyboard-layouts=us console=tty0 console=ttyS0,115200 loglevel=4']
  self.p=subprocess.Popen(cmd,env=env,stdout=subprocess.DEVNULL,stderr=(E/('toolbox-persistence-qemu-'+str(n)+'.log')).open('wb'))
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
subprocess.run([str(R/'build/qemu11/qemu-img'),'create','-f','qcow2','-F','raw','-b',str(iso),str(W/'fresh.qcow2'),'64000000000'],check=True,stdout=subprocess.DEVNULL)
(W/'fresh.qcow2').replace(usb)
g=None
try:
 g=Guest(1);g.login();g.send('sudo /usr/local/bin/gbrunch-storage');token=g.wait(r'Type SETUP ([0-9a-f]{12})');g.send('SETUP '+token.group(1));g.wait('Workspace created and GPT verified',timeout=300);g.wait('Press Enter to close:');g.send('');g.wait(r'live@[^: ]+:.*\$');g.shutdown();print('WORKSPACE_SETUP_PASS',flush=True)
 g=Guest(2);g.login();code="import subprocess,pathlib;w=pathlib.Path(subprocess.check_output(['findmnt','-nr','-S','LABEL=GBWORK','-o','TARGET'],text=True).splitlines()[0]);assert (w/'persistence.conf').read_text().strip()=='/ union';pathlib.Path('/home/live/toolbox-persistence-test.txt').write_text('persistent marker');print('PERSISTENCE_MARKER_WRITTEN')";g.python(code,'PERSISTENCE_MARKER_WRITTEN');g.wait(r'live@[^: ]+:.*\$');g.send('sudo /usr/local/bin/gbrunch-report');g.wait('Report saved locally:');g.wait('Press Enter to close:');g.send('');g.wait(r'live@[^: ]+:.*\$');g.shutdown();print('REPORT_AND_PERSISTENCE_WRITE_PASS',flush=True)
 g=Guest(3);g.login();code="import subprocess,pathlib,json,zipfile;assert pathlib.Path('/home/live/toolbox-persistence-test.txt').read_text()=='persistent marker';w=pathlib.Path(subprocess.check_output(['findmnt','-nr','-S','LABEL=GBWORK','-o','TARGET'],text=True).splitlines()[0]);reports=list((w/'reports').glob('*.zip'));assert reports;assert {'hardware-pci.txt','display-connectors.json','input-devices.txt','previous-toolbox-journal.txt'} <= set(zipfile.ZipFile(reports[0]).namelist());assert subprocess.check_output(['hostname'],text=True).strip()=='gbrunch-toolbox';subprocess.run(['dpkg-query','-W','lxpolkit','pipewire-pulse'],check=True);network=subprocess.check_output(['nmcli','-t','-f','DEVICE,TYPE,STATE','device'],text=True);assert 'ethernet:connected' in network;version=subprocess.check_output(['firefox-esr','--version'],text=True);print('TOOLKIT_TEST_JSON:'+json.dumps(dict(passed=True,real_64gb_usb_setup=True,iso_boot_partitions_preserved=True,desktop_overlay_persisted_across_reboot=True,report_zip_persisted=True,networkmanager_virtual_ethernet_connected=True,firefox_installed=version.strip(),scope='QEMU live USB; physical Wi-Fi and laptop graphics not tested')))";match=g.python(code,r'TOOLKIT_TEST_JSON:(\{[^\r\n]+\})');report=json.loads(match.group(1));g.wait(r'live@[^: ]+:.*\$');g.shutdown();(E/'toolbox-persistence-test.json').write_text(json.dumps(report,indent=2)+'\n');print('TOOLBOX_PERSISTENCE_PASS',json.dumps(report),flush=True)
 # Independently compare every original ISO partition's bytes after formatting.
 raw=W/'verified-usb.raw';subprocess.run([str(R/'build/qemu11/qemu-img'),'convert','-f','qcow2','-O','raw','-S','64k',str(usb),str(raw)],check=True)
 sys=__import__('sys');sys.path.insert(0,str(R/'tools'));from inspect_recovery import gpt
 def sha(path,off,n):
  h=hashlib.sha256()
  with open(path,'rb') as f:
   f.seek(off)
   while n:b=f.read(min(n,4<<20));assert b;h.update(b);n-=len(b)
  return h.hexdigest()
 with iso.open('rb') as f:parts=gpt(f)
 with raw.open('rb') as f:after=gpt(f)
 for p in parts:assert next(x for x in after if x['index']==p['index'])==p and sha(iso,p['offset'],p['bytes'])==sha(raw,p['offset'],p['bytes'])
 assert len(after)==len(parts)+1 and after[-1]['name']=='GBWORK';report['original_iso_efi_gap_bytes_verified_unchanged']=True;(E/'toolbox-persistence-test.json').write_text(json.dumps(report,indent=2)+'\n');raw.unlink();print('ISO_BOOT_BYTES_PRESERVATION_PASS',flush=True)
except Exception:
 if g:g.abort()
 raise
