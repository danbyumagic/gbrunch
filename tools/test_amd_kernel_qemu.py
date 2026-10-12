#!/usr/bin/env python3
"""Diskless QEMU smoke test for a newly built AMD kernel/module closure.
Tests boot and real module admission, not AMD hardware, firmware or Android UI.
Never loads modules on the host or attaches a host disk/network interface.
"""
import argparse
import gzip
import json
import pathlib
import struct
import subprocess


def modinfo(path):
    b=path.read_bytes()
    if b[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',b,18)[0]!=62:
        raise ValueError('Not an x86_64 kernel module: '+str(path))
    offset=struct.unpack_from('<Q',b,40)[0];size,count,si=struct.unpack_from('<HHH',b,58)
    sections=[struct.unpack_from('<IIQQQQIIQQ',b,offset+i*size) for i in range(count)]
    strings=sections[si];names=b[strings[4]:strings[4]+strings[5]]
    for s in sections:
        name=names[s[0]:names.find(b'\0',s[0])]
        if name==b'.modinfo':
            result={}
            for item in b[s[4]:s[4]+s[5]].split(b'\0'):
                if b'=' in item:
                    key,value=item.split(b'=',1);result.setdefault(key.decode(),[]).append(value.decode())
            return result
    raise ValueError('Module metadata missing: '+str(path))


def closure(modules, roots):
    selected=set();active=set();order=[]
    def visit(name):
        name=name.replace('-','_')
        if name in selected:return
        if name in active:raise ValueError('Module dependency cycle: '+name)
        if name not in modules:raise ValueError('Missing rebuilt module dependency: '+name)
        active.add(name)
        for dep in modinfo(modules[name]).get('depends',[''])[0].split(','):
            if dep:visit(dep)
        active.remove(name);selected.add(name);order.append(modules[name])
    for name in roots:visit(name)
    return order


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build','busybox','qemu','work'):
        p.add_argument('--'+name,type=pathlib.Path,required=True)
    p.add_argument('--qemu-data',type=pathlib.Path)
    p.add_argument('--bios',type=pathlib.Path)
    p.add_argument('--timeout',type=int,choices=range(30,601),default=180)
    args=p.parse_args()
    if args.work.exists():raise ValueError('Choose a fresh smoke-test output directory')
    kernel=args.build/'arch/x86/boot/bzImage'
    if not kernel.is_file():raise ValueError('Built kernel image missing')
    modules={}
    for file in args.build.rglob('*.ko'):
        name=file.stem.replace('-','_')
        if name in modules:raise ValueError('Ambiguous rebuilt module name: '+name)
        modules[name]=file
    order=closure(modules,['amdgpu'])
    release=(args.build/'include/config/kernel.release').read_text().strip()
    for module in order:
        magic=modinfo(module)['vermagic'][0]
        if magic.split()[0]!=release:raise ValueError('Module vermagic differs from the new kernel')
    args.work.mkdir(parents=True)
    out=bytearray()
    def entry(name,data,mode,major=0,minor=0):
        name=name.encode()+b'\0'
        fields=[1,mode,0,0,1,0,len(data),0,0,major,minor,len(name),0]
        out.extend(b'070701'+b''.join(f'{n:08x}'.encode() for n in fields)+name)
        out.extend(bytes(-len(out)%4));out.extend(data);out.extend(bytes(-len(out)%4))
    for directory in ['dev','proc','sys','bin','modules']:entry(directory,b'',0o40755)
    entry('dev/console',b'',0o20600,5,1)
    entry('bin/busybox',args.busybox.read_bytes(),0o100755)
    script='''#!/bin/busybox sh
export PATH=/bin
/bin/busybox --install -s /bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
exec >/dev/console 2>&1
uname -a
failed=0
'''
    for module in order:
        entry('modules/'+module.name,module.read_bytes(),0o100644)
        script+=f'insmod /modules/{module.name}\nrc=$?\necho AMD_MODULE_RESULT:{module.name}:$rc\n[ "$rc" -eq 0 ] || failed=1\n'
    script+='''if [ "$failed" -eq 0 ] && [ -d /sys/module/amdgpu ]; then
 echo AMD_KERNEL_MODULE_SMOKE_PASS
else
 echo AMD_KERNEL_MODULE_SMOKE_FAIL
fi
echo 'Scope: no AMD GPU is emulated; graphics, firmware and Android are untested'
dmesg
poweroff -f
'''
    entry('init',script.encode(),0o100755);entry('TRAILER!!!',b'',0)
    ramdisk=args.work/'smoke-initrd.gz';ramdisk.write_bytes(gzip.compress(out,mtime=0))
    command=[str(args.qemu.resolve()),'-machine','q35','-accel','tcg','-cpu','max','-m','768','-smp','2',
             '-kernel',str(kernel.resolve()),'-initrd',str(ramdisk.resolve()),
             '-append','rdinit=/init 8250.nr_uarts=1 console=ttyS0,115200 earlycon=uart8250,io,0x3f8 loglevel=8 ignore_loglevel drm.debug=0x1e panic=-1',
             '-display','none','-vga','none','-serial','stdio','-monitor','none','-nic','none','-no-reboot']
    if args.qemu_data:command+=['-L',str(args.qemu_data.resolve())]
    if args.bios:command+=['-bios',str(args.bios.resolve())]
    report={'scope':'kernel boot and module admission only; no AMD hardware/Android rendering',
            'kernel_release':release,'modules':[m.name for m in order],'command':command}
    with (args.work/'serial.log').open('wb') as log:
        try:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
            report['exit_code']=result.returncode
        except subprocess.TimeoutExpired:
            report['timeout']=True
    text=(args.work/'serial.log').read_text(errors='replace')
    report['passed']=(report.get('exit_code')==0 and 'AMD_KERNEL_MODULE_SMOKE_PASS' in text and
                      all('AMD_MODULE_RESULT:'+m.name+':0' in text for m in order) and 'Kernel panic' not in text)
    (args.work/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'report':str(args.work/'result.json')}))
    raise SystemExit(0 if report['passed'] else 1)

if __name__=='__main__':main()
