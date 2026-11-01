#!/usr/bin/env python3
"""Derive V8 from the tested V7 image: two init lines for USB (UVC) cameras, nothing else.

V7 imports Ruby's vendor init files explicitly and excludes init.insmod.rc, so system_heap.ko is never
loaded and /dev/dma_heap/system does not exist. Ruby's USB camera HAL then fails V4L2 buffer
allocation (V4L2Device(BufferAllocation)): the camera is listed and hot-plug works, but the preview
stays black. The excluded init.common.rc also creates /data/vendor/camera, used by the camera effects.

  build_compat_v8.py [--v7 compat.ext4] [--out DIR]
"""
import argparse,hashlib,json,os,pathlib,re,shutil,subprocess,tempfile
R=pathlib.Path(__file__).resolve().parents[1]
V7='77cb6ec0e399a944a020b5d7d55d03dbd1bb5a2ba01012be91d315987ab69722'
RC='/init.gbrunch.rc'
# (anchor, inserted after it). Each anchor occurs exactly once in V7's init.gbrunch.rc.
EDITS=[('on early-init\n','    insmod /vendor/lib/modules/system_heap.ko\n'),
       ('on post-fs-data\n','    mkdir /data/vendor/camera 0775 system camera\n')]
FAKE_TIME='1760072400'  # fixed e2fsprogs clock (2025-10-10T05:00:00Z) so the output is byte-reproducible

def tools():
    local=R/'tools/local/usr/sbin'
    e=dict(os.environ,E2FSPROGS_FAKE_TIME=FAKE_TIME)
    if (local/'debugfs').exists():
        e['LD_LIBRARY_PATH']=str(R/'tools/local/usr/lib/x86_64-linux-gnu')
        return str(local/'debugfs'),str(local/'e2fsck'),e
    return shutil.which('debugfs') or '/usr/sbin/debugfs',shutil.which('e2fsck') or '/usr/sbin/e2fsck',e

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

def build(v7,out):
    debugfs,e2fsck,env=tools()
    if sha(v7)!=V7:raise SystemExit('%s is not the tested V7 image'%v7)
    out.mkdir(parents=True,exist_ok=True);image=out/'compat.ext4';shutil.copyfile(v7,image)
    run=lambda *c:subprocess.run([debugfs,*c],check=True,capture_output=True,text=True,env=env).stdout
    with tempfile.TemporaryDirectory() as td:
        cur=pathlib.Path(td)/'cur';new=pathlib.Path(td)/'new'
        run('-R','dump %s %s'%(RC,cur),str(image));text=cur.read_text()
        label=run('-R','ea_get -V %s security.selinux'%RC,str(image)).strip()
        if not re.fullmatch(r'u:object_r:[a-z0-9_]+:s0',label):raise SystemExit('unexpected label %r'%label)
        for anchor,line in EDITS:
            if text.count(anchor)!=1:raise SystemExit('anchor %r not found exactly once'%anchor)
            text=text.replace(anchor,anchor+line)
        new.write_text(text);cmds=pathlib.Path(td)/'commands'
        cmds.write_text('\n'.join(['rm '+RC,'write %s %s'%(new,RC),'sif %s mode 0100644'%RC,'sif %s uid 0'%RC,
                                   'sif %s gid 0'%RC,'ea_set %s security.selinux %s'%(RC,label)])+'\n')
        run('-w','-f',str(cmds),str(image))
    subprocess.run([e2fsck,'-fn',str(image)],check=True,capture_output=True,env=env)
    manifest=dict(base_v7_sha256=V7,v8_sha256=sha(image),changed_files=[RC],
                  inserted_lines=[dict(after=a.strip(),line=l.strip()) for a,l in EDITS],
                  google_images_modified=False,physical_test='equivalent lines in the HP Dragonfly G4 profile: Buffalo BSW20KM11 UVC preview works')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--v7',type=pathlib.Path,default=R/'build/compat-wifi-v7/compat.ext4')
    p.add_argument('--out',type=pathlib.Path,default=R/'build/compat-camera-v8')
    a=p.parse_args();print(json.dumps(build(a.v7,a.out),indent=2))
