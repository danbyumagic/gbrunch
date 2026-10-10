#!/usr/bin/env python3
"""Apply verified local build-tool output to the disposable Work vendor view.

Regular owned QCOW2 file only. Requires all guests stopped; recovery is never
written. Linux memfd avoids a second full vendor image on the constrained disk.
"""
import hashlib,json,os,pathlib,struct,subprocess
from native_vendor_in_vm import RULES
R=pathlib.Path(__file__).resolve().parents[1]
def main():
    env=os.environ.copy();env['LD_LIBRARY_PATH']=str(R/'tools/local/usr/lib/x86_64-linux-gnu')
    mc=[str(R/'tools/local/usr/bin/mcopy'),'-i',str(R/'build/local-tool-vm/work.fat')]
    assert subprocess.check_output(mc+['::/status.txt','-'],env=env).strip()==b'0'
    result=json.loads(subprocess.check_output(mc+['::/result.json','-'],env=env))
    table=(R/'build/vendor-view-native/table.bin').read_bytes();location=None
    for i in range(128):
        e=table[i*128:(i+1)*128]
        if e[56:].decode('utf-16le').rstrip('\0')=='GBVENDOR':
            start,end=struct.unpack_from('<QQ',e,32);location=start*512;assert result['vendor_bytes']<=(end-start+1)*512
    assert location is not None
    b=subprocess.check_output(mc+['::/vendor.erofs','-'],env=env)
    assert len(b)==result['vendor_bytes'] and hashlib.sha256(b).hexdigest()==result['vendor_sha256']
    fd=os.memfd_create('gbrunch-verified-local-vendor');os.write(fd,b);del b
    try:subprocess.run([str(R/'build/qemu11/qemu-io'),'-f','qcow2','-c',f'write -s /proc/self/fd/{fd} {location} {result["vendor_bytes"]}',str(R/'build/vendor-view-native/recovery-vendor-view.qcow2')],pass_fds=(fd,),check=True)
    finally:os.close(fd)
    p=R/'build/vendor-view-native/manifest.json';m=json.loads(p.read_text());m.update(vendor_sha256=result['vendor_sha256'],policy_sha256=result['policy_sha256'],rules=RULES);p.write_text(json.dumps(m,indent=2)+'\n')
    (R/'evidence/local-tool-vm-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Verified and applied local vendor; original recovery untouched.')
if __name__=='__main__':main()
