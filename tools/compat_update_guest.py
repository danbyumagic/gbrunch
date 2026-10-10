#!/usr/bin/env python3
"""Read-only source SSD -> local vendor build; never write the physical SSD."""
import fcntl,hashlib,json,pathlib,struct,subprocess,sys
sys.path.insert(0,'/payload')
import native_vendor_in_vm as vendor
from maintain_userdata_guest import layout
W=pathlib.Path('/work');D=pathlib.Path('/dev/vdb')
def main():
 assert 'gbrunch.compat_update=1' in pathlib.Path('/proc/cmdline').read_text()
 with D.open('rb') as f:
  flag=bytearray(4);fcntl.ioctl(f.fileno(),0x125e,flag,True);assert struct.unpack('I',flag)[0]==1,'Source virtual disk must be read-only'
  prefix=f.read(17408)
 parts,u,*_=layout(D);by={p['name']:p for p in parts}
 assert vendor.OFFSET>=by['super']['offset'] and vendor.OFFSET+379772928<=by['super']['offset']+by['super']['bytes']
 current=subprocess.check_output(['/bin/dump.erofs','--offset='+str(by['GBVENDOR']['offset']),'--path=/etc/selinux/precompiled_sepolicy','--cat',str(D)])
 # Detect an unrelated vendor profile before constructing or applying a patch.
 original=subprocess.check_output(['/bin/dump.erofs','--offset='+str(vendor.OFFSET),'--path=/etc/selinux/precompiled_sepolicy','--cat',str(D)])
 assert hashlib.sha256(original).hexdigest()==json.loads((W/'request.json').read_text())['original_policy_sha256']
 base=W/'baseline-policy.bin';orig=W/'source-policy.bin';orig.write_bytes(original)
 subprocess.run(['/bin/extend-vendor-policy',str(orig),str(base),*vendor.RULES[:-len(vendor.GRAPHICS_RULES)]],check=True,stdout=subprocess.DEVNULL)
 vendor.main()
 result=json.loads((W/'result.json').read_text());assert result['vendor_bytes']<=by['GBVENDOR']['bytes'],'Updated vendor would exceed compatibility partition'
 new=(W/'new-policy.bin').read_bytes()
 assert hashlib.sha256(current).hexdigest() in [hashlib.sha256(base.read_bytes()).hexdigest(),'5e8dbfefccc80816fe5f1f3c52fa2019847d4a7eb8ea9591de0f8651b4b1cf0b',hashlib.sha256(new).hexdigest(),'9eb5b272c3b2c6cda83ab2b3339d9e6a9b252904195e6fbb67e6861438f622aa','a5f3616537afafe5e2f32fcb9ef016e6c00851a1f169afe82875fc2485073f39','42e2c1705f5ac402fda6b2e3b1cbc11671a5088317de077dae15a7b430c9143c'],'Existing GBVENDOR policy has an unsupported profile'
 checks=[]
 for policy,name in [(base,'policy-before.txt'),(W/'new-policy.bin','policy-after.txt')]:
  p=subprocess.run(['/bin/check-graphics-memfd-policy',str(policy)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True,text=True)
  (W/name).write_text(p.stdout);checks.append(p.stdout)
 assert checks[1].count('denied=00000000')==6 and 'u:r:isolated_app:s0:c522,c768 requested=00000416 allowed=00000000' in checks[1]
 domains=json.loads(pathlib.Path('/payload/graphics_client_domains.json').read_text())
 contexts=['u:r:'+d+':'+level for d in domains for level in ['s0','s0:c522,c768']]
 audit=subprocess.check_output(['/bin/check-graphics-memfd-policy',str(W/'new-policy.bin'),*contexts],text=True)
 (W/'graphics-client-audit.txt').write_text(audit)
 assert audit.count('denied=00000000')==len(contexts),'Incomplete application graphics access'
 result.update(graphics_client_domains=domains,graphics_context_checks=len(contexts))
 result.update(partitions=parts,primary_gpt_sha256=hashlib.sha256(prefix).hexdigest(),source_ssd_readonly=True,
  before_vendor_policy_sha256=hashlib.sha256(current).hexdigest(),scope='Local-only derived GBVENDOR build; original Google system and vendor source preserved',
  graphics_av_checks_passed=True)
 (W/'update-result.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
