#!/usr/bin/env python3
"""Read only the independent log partition from a stopped QEMU file fixture."""
import argparse,json,os,pathlib,subprocess,re
R=pathlib.Path(__file__).resolve().parents[1]
def read_logs(snapshot,partition=None,label='native-android'):
    m=partition or json.loads((R/'build/native-android-gpu/uefi-manifest.json').read_text())['log_partition']
    out=R/'extracted'/(label+'-fat-logs');out.mkdir(exist_ok=True)
    fat=out/'logs.fat'
    opts=f'driver=raw,offset={m["offset"]},size={m["bytes"]},file.driver=qcow2,file.file.driver=file,file.file.filename={snapshot.resolve()}'
    subprocess.run([str(R/'build/qemu11/qemu-img'),'convert','--image-opts',opts,'-O','raw','-S','64k',str(fat)],check=True)
    env=os.environ.copy();env['LD_LIBRARY_PATH']=str(R/'tools/local/usr/lib/x86_64-linux-gnu')
    listing=subprocess.run([str(R/'tools/local/usr/bin/mdir'),'-b','-i',str(fat),'::/Android-Logs'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,text=True)
    runs=re.findall(r'::/Android-Logs/(run-[^/\r\n]+)/?',listing.stdout)
    if runs:
        subprocess.run([str(R/'tools/local/usr/bin/mcopy'),'-s','-o','-i',str(fat),'::/Android-Logs/'+runs[-1],str(out)],env=env,check=True)
        run=out/runs[-1];result={}
        candidates={'logcat.txt':['startup-logcat.txt','live-logcat.txt','final-logcat.txt'],
                    'modules.txt':['*-modules.txt'],'drm-nodes.txt':['*-drm-nodes.txt'],
                    'properties.txt':['*-properties.txt'],'status.txt':['status.txt'],'commands-stderr.txt':['commands-stderr.txt']}
        for name,patterns in candidates.items():
            files=[p for pattern in patterns for p in sorted(run.glob(pattern))]
            result[name]={'present':bool(files),'bytes':sum(p.stat().st_size for p in files)}
        (R/'evidence'/(label+'-fat-log-readback.json')).write_text(json.dumps(result,indent=2)+'\n')
        return result
    result={}
    for name in ['logcat.txt','modules.txt','drm-nodes.txt','properties.txt']:
        proc=subprocess.run([str(R/'tools/local/usr/bin/mcopy'),'-i',str(fat),'::/Android-Logs/'+name,'-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        result[name]={'present':proc.returncode==0,'bytes':len(proc.stdout)}
        if proc.returncode==0:(out/name).write_bytes(proc.stdout)
    (R/'evidence'/(label+'-fat-log-readback.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('snapshot',type=pathlib.Path);a=p.parse_args()
    print(json.dumps(read_logs(a.snapshot),indent=2))
