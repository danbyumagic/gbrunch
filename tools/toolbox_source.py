#!/usr/bin/env python3
"""Verified local recovery QCOW2, exposed as a read-only NBD installer source."""
import pathlib,subprocess,json,hashlib,os,stat,time,contextlib
from dualboot_installer import require,identity,capacity,read_layout,COMPAT_HASH,EXPECTED,SOURCE_GUIDS,sha_range
from assemble_external_lab import RAW_HASH

RECORD=pathlib.Path('/run/gbrunch/local-source-verified.json')
def fingerprint(path):
 p=pathlib.Path(path).resolve();s=p.stat();require(stat.S_ISREG(s.st_mode),'Source artifact must be a regular file')
 return dict(path=str(p),inode=s.st_ino,device=s.st_dev,bytes=s.st_size,mtime_ns=s.st_mtime_ns)
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def workspace():
 rows=subprocess.check_output(['findmnt','-J','-S','LABEL=GBWORK','-o','TARGET,SOURCE,FSTYPE'],text=True)
 files=json.loads(rows)['filesystems'];require(len(files)==1,'Exactly one persistent GBWORK workspace is required')
 row=files[0];require(row['fstype']=='ext4','GBWORK must be ext4')
 node=(pathlib.Path('/sys/class/block')/pathlib.Path(row['source']).name).resolve()
 require((node/'partition').exists(),'Workspace must be a physical USB partition')
 parent=identity('/dev/'+node.parent.name);require(parent['usb'],'Workspace must be on USB')
 medium=subprocess.check_output(['findmnt','-nr','-o','SOURCE','--target','/run/live/medium'],text=True).strip()
 require((pathlib.Path('/sys/class/block')/pathlib.Path(medium).name).resolve().parent==node.parent,'Workspace must belong to the boot USB')
 require((pathlib.Path('/run/live/medium')/'GBRUNCH-TOOLBOX.txt').read_text().strip() in ('GBRUNCH toolbox v0.1','GBRUNCH toolbox v0.2','GBRUNCH toolbox v0.3'),'Not running from the toolbox')
 return pathlib.Path(row['target']).resolve(),parent
def verify_artifacts(image,expected_backing):
 image=pathlib.Path(image).resolve();base=pathlib.Path(expected_backing).resolve();manifest=image.with_name(image.name+'.manifest.json')
 before=[fingerprint(x) for x in (image,base,manifest)]
 md=json.loads(manifest.read_text());require(md['format']=='qcow2' and md['original_raw_sha256']==RAW_HASH,'Wrong recovery build manifest')
 chain=json.loads(subprocess.check_output(['qemu-img','info','--backing-chain','--output=json',str(image)],text=True))
 require(len(chain)==2 and chain[0]['format']=='qcow2' and chain[1]['format']=='raw','Only a local QCOW2 over the official raw recovery is supported')
 require(pathlib.Path(chain[0]['full-backing-filename']).resolve()==base and pathlib.Path(chain[1]['filename']).resolve()==base,'Unexpected backing file')
 print('Verifying official recovery and local build. No disk writes.',flush=True)
 require(sha(base)==RAW_HASH,'Official recovery hash mismatch')
 require(sha(image)==md['output_sha256'],'Local build hash mismatch')
 subprocess.run(['qemu-img','check','-f','qcow2',str(image)],check=True)
 require(before==[fingerprint(x) for x in (image,base,manifest)],'Artifacts changed during verification')
 return dict(artifacts=before,image_sha256=md['output_sha256'],manifest_sha256=sha(manifest),virtual_bytes=chain[0]['virtual-size'])
def verify_nbd_identity(path,st):
 p=pathlib.Path(path).resolve();require(RECORD.exists(),'Unverified NBD source')
 s=RECORD.stat();require(s.st_uid==0 and stat.S_IMODE(s.st_mode)==0o600,'Unsafe source verification record')
 record=json.loads(RECORD.read_text());require(record['nbd_path']==str(p) and record['rdev']==st.st_rdev,'Wrong NBD device')
 w,parent=workspace();require(parent==record['parent_usb'],'Boot USB identity changed')
 files=record['verification']['artifacts'];require(files==[fingerprint(x['path']) for x in files],'Verified source changed')
 require(sha(files[2]['path'])==record['verification']['manifest_sha256'],'Source manifest changed')
 image=pathlib.Path(files[0]['path']);require(image==w/'recovery/source.qcow2','Source must be the local workspace build')
 with p.open('rb') as f:require(__import__('struct').unpack('I',__import__('fcntl').ioctl(f,0x125e,bytes(4)))[0]==1,'NBD must remain read-only')
 require(capacity(p)==record['verification']['virtual_bytes'],'NBD size changed')
 pidfile=pathlib.Path(record['pid_file']);pid=int(pidfile.read_text());args=pathlib.Path('/proc')/str(pid)/'cmdline'
 require(str(image).encode() in args.read_bytes().split(b'\0'),'NBD server is not the verified image')
 return dict(path=str(p),bytes=capacity(p),rdev=st.st_rdev,sysfs=str((pathlib.Path('/sys/class/block')/p.name).resolve()),serial='LOCAL-IMAGE:'+parent['serial'],usb=True,local_image=record)
@contextlib.contextmanager
def local_source():
 require(os.geteuid()==0,'Run via sudo');w,parent=workspace();image=w/'recovery/source.qcow2';base=w/'recovery/ruby-recovery.raw'
 require(image.resolve()==image and base.resolve()==base,'Recovery paths must not escape the workspace')
 verification=verify_artifacts(image,base)
 subprocess.run(['modprobe','nbd','max_part=0'],check=True)
 require(not RECORD.exists(),'Another local source session is active')
 device=next((p for p in sorted(pathlib.Path('/sys/class/block').glob('nbd*')) if not (p/'pid').exists()),None)
 require(device is not None,'No unused NBD device');path='/dev/'+device.name
 RECORD.parent.mkdir(parents=True,exist_ok=True);pidfile=RECORD.parent/'local-source-nbd.pid';connected=False
 try:
  subprocess.run(['qemu-nbd','--read-only','--format=qcow2','--fork','--pid-file',str(pidfile),'--connect',path,str(image)],check=True);connected=True
  for _ in range(50):
   if capacity(path)==verification['virtual_bytes']:break
   time.sleep(.1)
  record=dict(nbd_path=path,rdev=os.stat(path).st_rdev,parent_usb=parent,pid_file=str(pidfile),verification=verification)
  fd=os.open(RECORD,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'w') as f:json.dump(record,f)
  identity(path);layout=read_layout(path);by={p['name']:p for p in layout['parts']}
  require(set(by)==EXPECTED,'Unexpected local recovery partition profile')
  require(all(by[n]['guid']==g for n,g in SOURCE_GUIDS.items()),'Wrong compatibility partition GUIDs')
  require(sha_range(path,by['GBRUNCH']['offset'],by['GBRUNCH']['bytes'])==COMPAT_HASH,'Wrong V7 compatibility bytes')
  yield path,w,parent
 finally:
  RECORD.unlink(missing_ok=True)
  if connected:subprocess.run(['qemu-nbd','--disconnect',path],check=True)
  pidfile.unlink(missing_ok=True)
