#!/usr/bin/env python3
"""Run a prepared Googlebook VM experiment using file-only disposable storage."""
import argparse, json, pathlib, subprocess, threading, time, socket
p=argparse.ArgumentParser(description=__doc__)
for name in ['qemu','kernel','initrd','disk','cmdline-file','work']:
    p.add_argument('--'+name,required=True,type=pathlib.Path)
p.add_argument('--capture-frame',action='store_true',help='Save a QMP screenshot near the end of the probe')
p.add_argument('--bios',type=pathlib.Path)
p.add_argument('--qemu-data',type=pathlib.Path)
p.add_argument('--seconds',type=int,default=180)
p.add_argument('--memory-mb',type=int,default=4096)
p.add_argument('--diagnostic-command',default='getprop sys.boot_completed; logcat -d -b all -t 500; dumpsys SurfaceFlinger')
a=p.parse_args()
if not 30<=a.seconds<=600: p.error('--seconds must be 30–600')
if not 2048<=a.memory_mb<=8192:p.error('--memory-mb must be 2048–8192')
for name in ['qemu','kernel','initrd','disk','cmdline_file']:
    value=getattr(a,name).resolve()
    if not value.is_file() or str(value).startswith('/dev/'):
        p.error(f'{name} must be a regular local file')
    setattr(a,name,value)
a.work.mkdir(parents=True,exist_ok=True)
log=a.work/'serial.log'
if log.exists(): p.error('Use a fresh work directory to preserve existing logs')
cmd=[str(a.qemu),'-machine','q35','-accel','tcg','-cpu','max','-m',str(a.memory_mb),'-smp','2','-vga','none','-device','virtio-gpu-pci,romfile=','-display','none','-serial','stdio','-monitor','none','-nic','none','-no-reboot','-kernel',str(a.kernel),'-initrd',str(a.initrd),'-append',a.cmdline_file.read_text().strip(),'-drive',f'if=none,id=os,format=qcow2,snapshot=on,file={str(a.disk).replace(",",",,")}','-device','nvme,drive=os,serial=GBRUNCHVM,addr=03.0']
if a.bios: cmd+=['-bios',str(a.bios.resolve())]
if a.qemu_data: cmd+=['-L',str(a.qemu_data.resolve())]
qmp_path=(a.work/'qmp.sock').resolve()
if a.capture_frame:
    if len(str(qmp_path).encode())>100: p.error('Work path too long for QMP socket')
    cmd+=['-qmp',f'unix:{qmp_path},server=on,wait=off']
started=time.monotonic()
with log.open('wb') as f:
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=f,stderr=subprocess.STDOUT)
    def diagnose():
        try:
            proc.stdin.write(('\r'+a.diagnostic_command+'\r').encode());proc.stdin.flush()
        except (BrokenPipeError,OSError): pass
    def capture():
        if not a.capture_frame:return
        try:
            with socket.socket(socket.AF_UNIX) as sock:
                sock.settimeout(5);sock.connect(str(qmp_path))
                stream=sock.makefile('rwb');stream.readline()
                for request in [{'execute':'qmp_capabilities'},{'execute':'screendump','arguments':{'filename':str((a.work/'frame.ppm').resolve())}}]:
                    stream.write((json.dumps(request)+'\n').encode());stream.flush()
                    while True:
                        response=json.loads(stream.readline())
                        if 'return' in response or 'error' in response:break
                    if 'error' in response:raise RuntimeError(str(response['error']))
        except (OSError,ValueError,RuntimeError) as error:
            (a.work/'frame-error.txt').write_text(str(error)+'\n')
    capture_timer=threading.Timer(a.seconds-15,capture);capture_timer.daemon=True;capture_timer.start()
    timer=threading.Timer(min(90,a.seconds-10),diagnose);timer.daemon=True;timer.start()
    timeout=False
    try: code=proc.wait(timeout=a.seconds)
    except subprocess.TimeoutExpired:
        timeout=True;proc.terminate()
        try: code=proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill();code=proc.wait()
    finally: timer.cancel();capture_timer.cancel();capture_timer.join(timeout=6);proc.stdin.close()
result={'command':cmd,'exit_code':code,'timeout':timeout,'duration_seconds':round(time.monotonic()-started,2),'storage':'disposable QEMU snapshot; no host devices','desktop_success':'not inferred from process exit status','log':str(log)}
(a.work/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'Experiment ended; inspect {log}. This does not establish desktop success.')
