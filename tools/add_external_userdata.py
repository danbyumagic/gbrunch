#!/usr/bin/env python3
"""Append fresh Android userdata to a NEW file-only QCOW2 view. Never writes devices."""
import argparse,hashlib,json,os,pathlib,struct,subprocess,tempfile,uuid,zlib

def run(*args,**kw):return subprocess.run([str(x) for x in args],check=True,**kw)
def relocate(header,table,sectors,start,length):
    h=bytearray(header);t=bytearray(table);n,esz=struct.unpack_from('<II',h,80)
    if h[:8]!=b'EFI PART' or n!=128 or esz!=128:raise ValueError('Unsupported GPT')
    saved=struct.unpack_from('<I',h,16)[0];struct.pack_into('<I',h,16,0)
    if zlib.crc32(h[:92])!=saved or zlib.crc32(t)!=struct.unpack_from('<I',h,88)[0]:raise ValueError('Invalid GPT CRC')
    entries=[]
    for i in range(n):
        e=t[i*esz:(i+1)*esz]
        if not any(e[:16]):continue
        a,b=struct.unpack_from('<QQ',e,32);entries.append((i,e[56:128].decode('utf-16le').rstrip('\0'),a,b))
    if len({x[1] for x in entries})!=len(entries):raise ValueError('Duplicate partition names')
    users=[x for x in entries if x[1]=='userdata']
    if len(users)!=1 or users[0][0]!=0:raise ValueError('Unexpected userdata entry')
    if any(b>=start for _,_,a,b in entries):raise ValueError('New userdata overlaps an existing partition')
    if start+length>sectors-33:raise ValueError('Insufficient image capacity')
    index=users[0][0];struct.pack_into('<QQ',t,index*esz+32,start,start+length-1)
    struct.pack_into('<Q',h,32,sectors-1);struct.pack_into('<Q',h,48,sectors-34);struct.pack_into('<I',h,88,zlib.crc32(t));struct.pack_into('<I',h,16,zlib.crc32(h[:92]))
    backup=bytearray(h);struct.pack_into('<QQ',backup,24,sectors-1,1);struct.pack_into('<Q',backup,72,sectors-33);struct.pack_into('<I',backup,16,0);struct.pack_into('<I',backup,16,zlib.crc32(backup[:92]));return h,t,backup

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--userdata-gib',type=int,choices=(16,32,64),default=16);a=p.parse_args()
    src=a.source.resolve();out=a.output.absolute()
    if not src.is_file() or str(src).startswith('/dev/') or out.exists() or out.is_symlink() or str(out.resolve()).startswith('/dev/'):p.error('Use an existing source file and a NEW regular output path; devices are forbidden')
    info=json.loads(subprocess.check_output(['qemu-img','info','--output=json',str(src)]))
    if info['format']!='qcow2':p.error('Source must be the locally assembled QCOW2 image')
    if not out.parent.is_dir():p.error('Output parent must exist')
    size=a.userdata_gib<<30;start=(info['virtual-size']+(1<<20)-1)//(1<<20)*(1<<20);total=start+size+(1<<20)
    with tempfile.TemporaryDirectory(prefix='gbrunch-fresh-',dir=out.parent) as td, tempfile.TemporaryDirectory(prefix='gbrunch-fs-',dir='/tmp') as fstd:
        d=pathlib.Path(td);prefix=d/'prefix';run('qemu-img','dd','-f','qcow2','if='+str(src),'of='+str(prefix),'bs=512','count=34',stdout=subprocess.DEVNULL)
        b=prefix.read_bytes();h,t,bh=relocate(b[512:1024],b[1024:17408],total//512,start//512,size//512)
        fs=pathlib.Path(fstd)/'userdata.ext4'
        with fs.open('xb') as f:f.truncate(size)
        features='none,has_journal,ext_attr,dir_index,filetype,extent,casefold,sparse_super,large_file,huge_file,uninit_bg,dir_nlink,extra_isize,quota,project,verity'
        run('mke2fs','-q','-F','-t','ext4','-b','4096','-I','512','-i','16384','-m','0','-O',features,'-E','encoding=utf8-12.1,lazy_itable_init=0,lazy_journal_init=0,nodiscard','-J','size=64',fs)
        run('e2fsck','-fn',fs)
        # Keep construction separate; no result path is published until checks pass.
        view=d/'image.qcow2';run('qemu-img','create','-f','qcow2','-F','qcow2','-b',src,view,str(total),stdout=subprocess.DEVNULL)
        def write(data,offset):
            tmp=d/'chunk';tmp.write_bytes(data);run('qemu-io','-f','qcow2','-c',f'write -s {tmp} {offset} {len(data)}',view,stdout=subprocess.DEVNULL)
        mbr=bytearray(b[:512]);struct.pack_into('<I',mbr,458,min(total//512-1,0xffffffff))
        for off,data in [(0,mbr),(512,h),(1024,t),(total-33*512,t),(total-512,bh)]:write(data,off)
        with fs.open('rb') as f:
            off=0
            while data:=f.read(1<<20):
                if data.strip(b'\0'):write(data,start+off)
                off+=len(data)
        run('qemu-img','check','-f','qcow2',view)
        # Verify on-disk GPT, fresh filesystem features/size, and every other entry.
        readback=d/'readback';run('qemu-img','dd','-f','qcow2','if='+str(view),'of='+str(readback),'bs=512','count=34',stdout=subprocess.DEVNULL)
        actual=readback.read_bytes();assert actual[512:1024]==h and actual[1024:17408]==t
        assert t[128:]==b[1152:17408], 'Non-userdata partition entry changed'
        os.rename(view,out)
        result={'scope':'file-only traditional HP external layout; not the one-partition experiment','source':str(src),'userdata_gib':a.userdata_gib,'userdata_offset':start,'bytes':total,'original_system_partitions_changed':False,'fresh_filesystem_readonly_fsck_passed':True,'physical_hp_tested_for_this_build':False,'distribution':'Local use only; do not upload Google-derived images'}
        out.with_suffix(out.suffix+'.userdata.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
if __name__=='__main__':main()
