#!/usr/bin/env python3
"""Original kernel/Xe dependency admission in QEMU; does not emulate Intel GPU hardware."""
import gzip,json,pathlib,subprocess,shutil,time
R=pathlib.Path(__file__).resolve().parents[1];O=R/'build/xe-probe';B=R/'build/hp-diagnostics';Q=R/'tools/qemu'
def entry(name,data,mode,ino):
 n=name.encode()+b'\0';fields=[ino,mode,0,0,1,0,len(data),0,0,0,0,len(n),0]
 h=b'070701'+b''.join(f'{x:08x}'.encode() for x in fields)+n;h+=bytes(-len(h)%4);h+=data;return h+bytes(-len(data)%4)
data=gzip.decompress((B/'google-initrd.gz').read_bytes());extra=[];ino=950000
for name in ['xe','lib/firmware','lib/firmware/i915']:extra.append(entry(name,b'',0o040755,ino));ino+=1
for directory,prefix in [(O/'modules','xe'),(O/'firmware/i915','lib/firmware/i915')]:
 for p in sorted(directory.iterdir()):extra.append(entry(prefix+'/'+p.name,p.read_bytes(),0o100644,ino));ino+=1
extra.append(entry('etc/xe-load-order',(O/'module-load-order').read_bytes(),0o100644,ino));ino+=1
script=(R/'tools/hp_probe_init.sh').read_text()
insert='''while read filename; do
 insmod "/xe/$filename"
 rc=$?
 echo "GBRUNCH_XE_MODULE_RESULT $filename status=$rc" > /dev/kmsg
done < /etc/xe-load-order
'''
script=script.replace('load_modules >',insert+'\nload_modules >')
extra.append(entry('init',script.encode(),0o100755,ino));ino+=1;extra.append(entry('TRAILER!!!',b'',0,ino))
initrd=O/'xe-admission-initrd.gz';initrd.write_bytes(gzip.compress(data+b''.join(extra),compresslevel=6,mtime=0))
cmd=[str(R/'build/qemu11/qemu-system-x86_64'),'-L',str(Q/'usr/share/qemu'),'-machine','q35','-accel','tcg','-cpu','max','-m','1536','-smp','2','-vga','none','-display','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-bios',str(Q/'usr/share/seabios/bios-256k.bin'),'-kernel',str(R/'extracted/ruby/boot_a/kernel'),'-initrd',str(initrd),'-append','rdinit=/init console=ttyS0,115200 earlycon=uart8250,io,0x3f8,115200 8250.nr_uarts=4 loglevel=8 ignore_loglevel printk.time=1 panic=0 gbrunch.autopoweroff=1']
log=R/'evidence/original-xe-module-admission.log';start=time.monotonic()
with log.open('wb') as out:
 p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT)
 try:code=p.wait(timeout=80);timeout=False
 except subprocess.TimeoutExpired:p.terminate();code=p.wait(timeout=10);timeout=True
s=log.read_text(errors='replace');expected=(O/'module-load-order').read_text().splitlines();results={n:('GBRUNCH_XE_MODULE_RESULT '+n+' status=0') in s for n in expected}
report={'scope':'Actual original-kernel module admission, no Intel GPU emulation/physical claim','module_results':results,'seconds':round(time.monotonic()-start,2),'exit_code':code,'timeout':timeout,'kernel_panic':'Kernel panic' in s,'unknown_symbol':'Unknown symbol' in s,'desktop':'not tested'}
(R/'evidence/original-xe-module-admission.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert all(results.values()) and not timeout and not report['kernel_panic'],report
