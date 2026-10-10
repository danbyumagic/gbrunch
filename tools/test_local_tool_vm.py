#!/usr/bin/env python3
import json,os,pathlib,subprocess,time
R=pathlib.Path(__file__).resolve().parents[1]
w=R/'build/local-tool-vm';q=R/'tools/qemu'
cmd=json.loads((R/'evidence/local-tool-vm-test.json').read_text())['command']
if '-bios' not in cmd:cmd+=['-bios',str(q/'usr/share/seabios/bios-256k.bin')]
env=os.environ.copy();env['LD_LIBRARY_PATH']=str(q/'usr/lib/x86_64-linux-gnu')
start=time.monotonic()
with (R/'evidence/local-tool-vm-test.log').open('wb') as out:
 p=subprocess.Popen(cmd,stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env)
 try:code=p.wait(timeout=240);timeout=False
 except subprocess.TimeoutExpired:p.terminate();code=p.wait(timeout=10);timeout=True
(R/'evidence/local-tool-vm-test.json').write_text(json.dumps({'command':cmd,'exit_code':code,'timeout':timeout,'seconds':round(time.monotonic()-start,2),'scope':'isolated tools, regular disk files, read-only original recovery'},indent=2)+'\n')
print(code,timeout)
