#!/usr/bin/env python3
"""Local vendor derivation inside the owned, isolated build-tool VM only.

The recovery is a read-only virtual disk. Outputs stay on the local work disk.
No output containing Google vendor bytes may be included in a public kit.
"""
import hashlib,io,json,pathlib,re,runpy,struct,subprocess,tarfile

W=pathlib.Path('/work')
SOURCE=pathlib.Path('/dev/vdb')
OFFSET=6289358848  # Pinned Ruby 16452207 vendor_a extent.
RULES=['init','vendor_configs_file','file','mounton','init','system_file','file','mounton',
       'init','serial_device','chr_file','open,read,write,getattr,ioctl',
       'hal_keymint_default','vendor_boot_security_patch_level_prop','file','open,read,getattr,map',
       'hal_keymint_default','serialno_prop','file','open,read,getattr,map',
       'init','shell_data_file','filesystem','relabelto,relabelfrom,mount',
       'shell_data_file','shell_data_file','filesystem','associate',
       'vendor_init','vendor_boot_security_patch_level_prop','property_service','set',
       'shell','kernel','system','syslog_read',
       'shell','shell','capability2','syslog',
       'shell','proc_pressure_cpu','file','open,read,getattr',
       'shell','proc_pressure_mem','file','open,read,getattr',
       'shell','proc_pressure_io','file','open,read,getattr',
       'init','sysfs','file','open,write,getattr,setattr',
       'init','init','capability','sys_module',
       'init','vendor_file','system','module_load',
       'init','vendor_kernel_modules','system','module_load',
       'init','system_dlkm_file','system','module_load',
       'shell','vendor_default_prop','file','open,read,getattr,map',
       'shell','sysfs','file','open,read,getattr']
# Application domains audited from the pinned source policy. Keep
# enforcing mode and limit the new access to graphics metadata buffers.
GRAPHICS_RULES=[]
for domain in json.loads(pathlib.Path(__file__).with_name('graphics_client_domains.json').read_text()):
    GRAPHICS_RULES += [domain,'hal_graphics_allocator_default','memfd_file','read,write,getattr,map']
RULES += GRAPHICS_RULES
TOOLS=['futility','crossystem','flashrom','fwtool','fwupd-binder',
       'fwupd_blocking_update','gscutil','gscd','gsctool','vpd']

def main():
    assert 'gbrunch.toolvm=1' in pathlib.Path('/proc/cmdline').read_text()
    assert (W/'GBRUNCH-BUILD-MARKER.txt').read_text()=='GBRUNCH local build-tool work disk\n'
    meta=runpy.run_path('/payload/erofs_metadata.py')['metadata']
    meta.__globals__['D']=pathlib.Path('/bin/dump.erofs')
    def run(*args,**kw):return subprocess.run([str(a) for a in args],check=True,**kw)
    def extract(name):
        return subprocess.check_output(['/bin/dump.erofs','--offset='+str(OFFSET),'--path='+name,'--cat',str(SOURCE)])
    original=W/'original-policy.bin';original.write_bytes(extract('/etc/selinux/precompiled_sepolicy'))
    policy=W/'new-policy.bin'
    with (W/'policy-changes.txt').open('wb') as f:run('/bin/extend-vendor-policy',original,policy,*RULES,stdout=f)
    overlays={'etc/selinux/precompiled_sepolicy':policy.read_bytes()}
    for n in TOOLS:
        check=subprocess.run(['/bin/dump.erofs','--offset='+str(OFFSET),'--path=/bin/'+n,str(SOURCE)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        if check.returncode==0 and re.search(r'NID: \d+',check.stdout):overlays['bin/'+n]=b'#!/system/bin/sh\necho GBRUNCH_HARDWARE_MAINTENANCE_DISABLED >&2\nexit 1\n'
    with tarfile.open(W/'overlay.tar','w',format=tarfile.PAX_FORMAT) as t:
        parents={'.'}
        for n in overlays:
            parts=pathlib.PurePosixPath(n).parts[:-1]
            for i in range(1,len(parts)+1):parents.add('/'.join(parts[:i]))
        for n in sorted(parents):
            m=meta(SOURCE,'/' if n=='.' else '/'+n,OFFSET)
            ti=tarfile.TarInfo(n);ti.type=tarfile.DIRTYPE;ti.mode=m['mode']&0o7777;ti.uid=m['uid'];ti.gid=m['gid'];ti.mtime=m['mtime']
            ti.pax_headers={} if n=='.' else {'SCHILY.xattr.'+k:v.decode() for k,v in m['xattrs'].items()};t.addfile(ti)
        for n,b in overlays.items():
            m=meta(SOURCE,'/'+n,OFFSET);ti=tarfile.TarInfo(n);ti.size=len(b);ti.mode=m['mode']&0o7777;ti.uid=m['uid'];ti.gid=m['gid'];ti.mtime=m['mtime']
            ti.pax_headers={'SCHILY.xattr.'+k:v.decode() for k,v in m['xattrs'].items()};t.addfile(ti,io.BytesIO(b))
    image=W/'vendor.erofs'
    with SOURCE.open('rb') as f:
        f.seek(OFFSET+1024);sb=f.read(128);assert sb[:4]==bytes.fromhex('e2e1f5e0')
        bs=1<<sb[12];size=struct.unpack_from('<I',sb,36)[0]*bs
        root_offset=struct.unpack_from('<I',sb,40)[0]*bs+struct.unpack_from('<H',sb,14)[0]*32
        f.seek(OFFSET+root_offset);oldroot=f.read(64);f.seek(OFFSET)
        with image.open('wb') as out:
            left=size
            while left:
                b=f.read(min(left,1048576));assert b;out.write(b);left-=len(b)
    run('/bin/mkfs.erofs','--incremental=data','--tar=f','-x0','-b4096','-T1230768000','-zlz4hc',image,W/'overlay.tar')
    with image.open('r+b') as f:
        f.seek(root_offset);newroot=f.read(64)
        assert oldroot[2:4]==newroot[2:4] and not(oldroot[0]&1 or newroot[0]&1)
        f.seek(root_offset+32);f.write(oldroot[32:48]);f.seek(1024)
        b=bytearray(f.read(bs-1024));b[4:8]=bytes(4);crc=0xffffffff
        for v in b:
            crc^=v
            for _ in range(8):crc=(crc>>1)^(0x82f63b78 if crc&1 else 0)
        f.seek(1028);f.write(struct.pack('<I',crc))
    run('/bin/fsck.erofs',image)
    got=subprocess.check_output(['/bin/dump.erofs','--path=/etc/selinux/precompiled_sepolicy','--cat',str(image)])
    assert got==policy.read_bytes()
    for n,b in overlays.items():
        assert subprocess.check_output(['/bin/dump.erofs','--path=/'+n,'--cat',str(image)])==b
    module_dir=W/'modules';module_dir.mkdir(exist_ok=True)
    for m in json.loads(pathlib.Path('/payload/modules.json').read_text()):
        b=subprocess.check_output(['/bin/dump.erofs','--offset='+str(m['offset']),'--path='+m['path'],'--cat',str(SOURCE)])
        assert hashlib.sha256(b).hexdigest()==m['sha256']
        (module_dir/m['file']).write_bytes(b)
    result={'vendor_bytes':image.stat().st_size,'vendor_sha256':hashlib.file_digest(image.open('rb'),'sha256').hexdigest(),
            'policy_sha256':hashlib.sha256(policy.read_bytes()).hexdigest(),'maintenance_stubs':list(overlays)[1:],
            'system_partitions':'untouched','distribution':'local-only generated vendor; never include in public kit'}
    (W/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
