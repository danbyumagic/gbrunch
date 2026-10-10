#!/usr/bin/env python3
"""Local diagnostic report; never uploads, reads credentials, or repairs a disk."""
import pathlib,subprocess,json,datetime,zipfile,os,shutil,sys
COMMANDS={'hardware-pci.txt':['lspci','-nnk'],'hardware-usb.txt':['lsusb'],'hardware-dmi.txt':['dmidecode','-t','system','-t','baseboard'],'kernel.txt':['dmesg','--color=never'],'disks.json':['lsblk','-J','-o','NAME,PATH,SIZE,TYPE,FSTYPE,LABEL,PARTLABEL,TRAN,MODEL'],'network.txt':['nmcli','device','status'],'wireless.txt':['iw','dev'],'rfkill.txt':['rfkill','list'],'audio.txt':['aplay','-l'],'kernel-modules.txt':['lsmod'],'kernel-version.txt':['uname','-a'],'input-devices.txt':['cat','/proc/bus/input/devices'],'previous-toolbox-journal.txt':['journalctl','-b','-1','--no-pager','-n','2000']}
def main():
 p=subprocess.run(['findmnt','-nr','-S','LABEL=GBWORK','-o','TARGET'],text=True,capture_output=True)
 base=pathlib.Path(p.stdout.splitlines()[0])/'reports' if p.returncode==0 and p.stdout.strip() else pathlib.Path('/home/live/gbrunch-reports')
 base.mkdir(parents=True,exist_ok=True);session=base/('report-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S'));session.mkdir()
 for name,cmd in COMMANDS.items():
  try:r=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30);text=r.stdout
  except Exception as exc:text=repr(exc)
  (session/name).write_text(text)
 display=[]
 for node in pathlib.Path('/sys/class/drm').glob('*'):
  if not (node/'status').exists():continue
  row={'connector':node.name}
  for name in ['status','modes']:
   try:row[name]=(node/name).read_text().strip()
   except OSError:pass
  try:row['edid_hex']=(node/'edid').read_bytes().hex()
  except OSError:pass
  display.append(row)
 (session/'display-connectors.json').write_text(json.dumps(display,indent=2)+'\n')
 (session/'PRIVACY.txt').write_text('Review before sharing. Hardware serial numbers, MAC/IP addresses and kernel/log identifiers may be present. No account files, browser state, Wi-Fi passwords, API keys or process environment are intentionally collected. Logs may still contain personal information. Nothing is automatically uploaded.\n')
 if '--android-logs' in sys.argv:collect_android(session)
 output=session.with_suffix('.zip')
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
  for f in session.rglob('*'):
   if f.is_file():z.write(f,f.relative_to(session))
 if os.geteuid()==0:
  os.chown(base,1000,1000);os.chown(output,1000,1000)
 print('Report saved locally: '+str(output)+'\nReview PRIVACY.txt and the contents before sharing.')
 if not p.stdout.strip():print('Temporary session: copy the ZIP elsewhere before rebooting.')
def collect_android(session):
 rows=json.loads(subprocess.check_output(['lsblk','-J','-o','PATH,TYPE,LABEL,FSTYPE']))['blockdevices'];parts=[]
 def walk(rows):
  for p in rows:
   if p.get('type')=='part' and p.get('label')=='GBRUNCH_LOG' and p.get('fstype')=='vfat':parts.append(p['path'])
   walk(p.get('children',[]))
 walk(rows);(session/'android-log-disks.json').write_text(json.dumps(parts));total=0;count=0
 for i,dev in enumerate(parts):
  mount=pathlib.Path('/run/gbrunch/report-mount-'+str(i));mount.mkdir(parents=True,exist_ok=True)
  try:
   subprocess.run(['mount','-t','vfat','-o','ro,nosuid,nodev,noexec',dev,str(mount)],check=True)
   dest=session/('android-'+pathlib.Path(dev).name);dest.mkdir()
   for f in mount.rglob('*'):
    if not f.is_file() or f.suffix.lower() not in ('.txt','.log','.json'):continue
    length=f.stat().st_size
    if count>=512 or total+length>50*(1<<20):continue
    out=dest/f.relative_to(mount);out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,out);total+=length;count+=1
  except Exception as exc:(session/('android-error-'+str(i)+'.txt')).write_text(repr(exc))
  finally:subprocess.run(['umount',str(mount)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
if __name__=='__main__':
 try:main()
 except Exception:__import__('traceback').print_exc()
 input('Press Enter to close: ')
