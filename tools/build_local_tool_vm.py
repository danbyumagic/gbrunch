#!/usr/bin/env python3
"""Package only open-source Linux/Python/EROFS build tools for local Mac assembly.

No Google recovery, system, vendor, policy or ramdisk is included. QEMU exposes
only regular local files; this VM never runs on the HP or sees physical disks.
"""
import gzip,hashlib,json,lzma,os,pathlib,re,shutil,stat,subprocess,sys
from prepare_native_android_gpu import entry

R=pathlib.Path(__file__).resolve().parents[1]
O=R/'build/local-tool-vm';O.mkdir(exist_ok=True)
L=R/'tools/local'
entries={};origins={}
def add(name,b,mode,source):
    entries[name]=(mode,b)
    origins[name]={'source':str(source),'sha256':hashlib.sha256(b).hexdigest()}
def copy(path,name,executable=False):
    p=pathlib.Path(path);add(name,p.read_bytes(),stat.S_IFREG|(0o755 if executable else 0o644),p)
def libs(p,environment=None):
    s=subprocess.check_output(['ldd',str(p)],env=environment,text=True,stderr=subprocess.DEVNULL)
    for line in s.splitlines():
        match=re.search(r'=>\s+(\S+)\s+\(',line)
        if match:
            source=pathlib.Path(match[1]).resolve();name='lib/x86_64-linux-gnu/'+source.name
            # Keep the SONAME name, not a resolved versioned file basename.
            name='lib/x86_64-linux-gnu/'+pathlib.Path(match[1]).name
            copy(source,name,True)
        else:
            match=re.search(r'^\s*(/\S+)\s+\(',line)
            if match:copy(pathlib.Path(match[1]),match[1].lstrip('/'),True)

def main():
    copy(L/'usr/bin/busybox','bin/busybox',True)
    apps=subprocess.check_output([str(L/'usr/bin/busybox'),'--list'],text=True).splitlines()
    for name in apps:
        if name!='busybox':add('bin/'+name,b'busybox',stat.S_IFLNK|0o777,'busybox applet')
    copy(R/'build/extend-vendor-policy-static','bin/extend-vendor-policy',True)
    copy('/lib/x86_64-linux-gnu/libgcc_s.so.1','lib/x86_64-linux-gnu/libgcc_s.so.1',True)
    env=os.environ.copy();env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
    for n in ['mkfs.erofs','fsck.erofs','dump.erofs']:
        p=L/'usr/bin'/n;copy(p,'bin/'+n,True);libs(p,env)
    python=pathlib.Path(sys.executable);copy(python,'usr/bin/python3',True);libs(python)
    base=pathlib.Path(sys.base_prefix)/'lib'/('python'+str(sys.version_info.major)+'.'+str(sys.version_info.minor))
    forbidden={'site-packages','__pycache__','ensurepip','idlelib','tkinter','turtledemo','test','tests'}
    for p in sorted(base.rglob('*')):
        rel=p.relative_to(base)
        if any(x in forbidden for x in rel.parts) or not p.is_file():continue
        copy(p,'usr/lib/'+base.name+'/'+str(rel),p.suffix=='.so')
        if p.suffix=='.so':libs(p)
    copy(R/'tools/native_vendor_in_vm.py','payload/native_vendor_in_vm.py')
    copy(O/'modules.json','payload/modules.json')
    copy(R/'sources/gbos-vm/image/erofs_metadata.py','payload/erofs_metadata.py')
    rows=json.loads((R/'build/hp-diagnostics/linux-modules.json').read_text())
    index={m['name']:m for m in rows};selected={};order=[]
    version=next((R/'tools/hp-kernel/usr/lib/modules').iterdir()).name
    files={p.name.removesuffix('.xz'):p for p in (R/'tools/hp-kernel/usr/lib/modules'/version).rglob('*.ko.xz')}
    def select(n):
        n=n.replace('-','_')
        if n in selected or n not in index:return
        m=index[n];selected[n]=m
        for dep in next((x[8:] for x in m['modinfo'] if x.startswith('depends=')),'').split(','):
            if dep:select(dep)
        order.append(n)
    for n in ['virtio_pci','virtio_blk','vfat','nls_cp437','nls_ascii','nls_utf8']:select(n)
    for n in order:
        m=selected[n];b=lzma.decompress(files[m['file']].read_bytes());assert hashlib.sha256(b).hexdigest()==m['sha256']
        add('modules/'+m['file'],b,stat.S_IFREG|0o644,files[m['file']])
    add('etc/module-order',('\n'.join(selected[n]['file'] for n in order)+'\n').encode(),stat.S_IFREG|0o644,'owned matching-module list')
    script='''#!/bin/sh
export PATH=/bin:/usr/bin
export PYTHONHOME=/usr
export PYTHONDONTWRITEBYTECODE=1
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mount -t tmpfs tmpfs /run
while read module; do insmod /modules/$module || echo TOOL_MODULE_FAILED:$module; done < /etc/module-order
mdev -s
if mount -t vfat /dev/vda /work; then
 if [ "$(cat /work/GBRUNCH-BUILD-MARKER.txt)" = 'GBRUNCH local build-tool work disk' ]; then
  python3 /payload/native_vendor_in_vm.py > /work/build-log.txt 2>&1
  result=$?
  echo $result > /work/status.txt
  cat /work/build-log.txt
  sync
 fi
 umount /work
fi
poweroff -f
'''
    add('init',script.encode(),stat.S_IFREG|0o755,'owned isolated tool-VM init')
    dirs={'dev','proc','sys','run','tmp','work','payload','modules','etc'}
    for n in entries:
        parts=pathlib.PurePosixPath(n).parts[:-1]
        for i in range(1,len(parts)+1):dirs.add('/'.join(parts[:i]))
    all_entries={n:(stat.S_IFDIR|0o755,b'') for n in sorted(dirs)};all_entries.update(entries)
    blob=b''.join(entry(n,b,mode,980000+i) for i,(n,(mode,b)) in enumerate(all_entries.items()))
    blob+=entry('TRAILER!!!',b'',0,999999)
    (O/'initrd.gz').write_bytes(gzip.compress(blob,mtime=0))
    kernel=R/'tools/hp-kernel/boot'/('vmlinuz-'+version);shutil.copyfile(kernel,O/'linux-kernel')
    manifest={'scope':'redistributable build tools only; no Google recovery components',
              'kernel_package':json.loads((R/'evidence/hp-diagnostic-kernel-package.json').read_text()),
              'python':sys.version,'modules':[selected[n]['file'] for n in order],
              'files':origins,'initrd_sha256':hashlib.sha256((O/'initrd.gz').read_bytes()).hexdigest(),
              'linux_kernel_sha256':hashlib.sha256((O/'linux-kernel').read_bytes()).hexdigest()}
    (O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Tool VM:',(O/'initrd.gz').stat().st_size,'bytes initrd; open-source Linux kernel only')

if __name__=='__main__':main()
