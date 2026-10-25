#!/usr/bin/env python3
"""File-only nested-GPT prototype. No physical device or Android installer support."""
import argparse,gzip,hashlib,json,pathlib,struct,subprocess,uuid,zlib

def gpt_image(path, payloads):
    """New disposable GPT file, partitions aligned to MiB boundaries."""
    entries=bytearray(128*128);offset=1<<20;placements=[]
    for index,(name,payload) in enumerate(payloads):
        length=(payload.stat().st_size+(1<<20)-1)//(1<<20)*(1<<20)
        e=bytearray(128);e[:16]=uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le
        e[16:32]=uuid.uuid4().bytes_le
        struct.pack_into('<QQQ',e,32,offset//512,(offset+length)//512-1,0)
        encoded=name.encode('utf-16le');e[56:56+len(encoded)]=encoded
        entries[index*128:(index+1)*128]=e;placements.append((offset,payload));offset+=length
    sectors=(offset+(1<<20))//512
    def header(current,other,table):
        h=bytearray(512);h[:8]=b'EFI PART';struct.pack_into('<IIII',h,8,0x10000,92,0,0)
        struct.pack_into('<QQQQ',h,24,current,other,34,sectors-34);h[56:72]=disk_guid
        struct.pack_into('<QIII',h,72,table,128,128,zlib.crc32(entries))
        struct.pack_into('<I',h,16,zlib.crc32(h[:92]));return h
    disk_guid=uuid.uuid4().bytes_le;mbr=bytearray(512);mbr[450]=0xee
    struct.pack_into('<II',mbr,454,1,sectors-1);mbr[510:]=b'\x55\xaa'
    with path.open('xb') as f:
        f.truncate(sectors*512)
        for off,data in [(0,mbr),(512,header(1,sectors-1,2)),(1024,entries),((sectors-33)*512,entries),((sectors-1)*512,header(sectors-1,1,sectors-33))]:
            f.seek(off);f.write(data)
        for off,payload in placements:
            f.seek(off)
            with payload.open('rb') as src:
                while chunk:=src.read(1<<20):
                    if any(chunk):f.write(chunk)
                    else:f.seek(len(chunk),1)
    return placements

def cpio(files):
    out=bytearray()
    for i,(name,data,mode) in enumerate([*files,('TRAILER!!!',b'',0)]):
        n=name.encode()+b'\0';fields=[i+1,mode,0,0,1,0,len(data),0,0,0,0,len(n),0]
        out.extend(b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n)
        out.extend(bytes(-len(out)%4));out.extend(data);out.extend(bytes(-len(out)%4))
    return gzip.compress(out,mtime=0)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['work','kernel','busybox','mkfs','qemu','qemu-data','bios']:
        p.add_argument('--'+name,type=pathlib.Path,required=True)
    p.add_argument('--debugfs',type=pathlib.Path,help='Optional read-only fixture integrity readback')
    p.add_argument('--modules',type=pathlib.Path,nargs='*',default=[])
    a=p.parse_args()
    for key in ['work','kernel','busybox','mkfs','qemu','qemu_data','bios']:
        value=getattr(a,key).absolute()
        if str(value).startswith('/dev/'):raise ValueError('Device paths are forbidden')
        setattr(a,key,value)
    if a.work.exists():raise ValueError('Use a new work directory')
    a.work.mkdir(parents=True)
    def fs(name,size,contents):
        tree=a.work/(name+'-files');tree.mkdir()
        for n,content in contents.items():
            dest=tree/n;dest.parent.mkdir(parents=True,exist_ok=True)
            if isinstance(content,pathlib.Path):
                with content.open('rb') as src,dest.open('wb') as out:
                    while chunk:=src.read(1<<20):out.write(chunk)
            else:dest.write_text(content)
        target=a.work/(name+'.ext4')
        with target.open('xb') as f:f.truncate(size)
        subprocess.run([str(a.mkfs),'-q','-F','-t','ext4','-m','0','-O','^metadata_csum_seed,^orphan_file','-d',str(tree),str(target)],check=True)
        return target
    system=fs('system',8<<20,{'marker':'GOOGLEBOOK_SYSTEM_FIXTURE\n'})
    data=fs('userdata',8<<20,{})
    image=a.work/'googlebook.img';gpt_image(image,[('system_a',system),('userdata',data)])
    hostfs=fs('host',64<<20,{'CONTAINER-TEST.txt':'GBRUNCH FILE-ONLY FIXTURE\n','googlebook.img':image})
    host=a.work/'one-partition.raw';gpt_image(host,[('GBRUNCH',hostfs)])
    entries=[('bin',b'',0o40755),('modules',b'',0o40755),('bin/busybox',a.busybox.read_bytes(),0o100755),('init',pathlib.Path(__file__).with_name('init.sh').read_bytes(),0o100755),('modules/order',('\n'.join(m.name for m in a.modules)+'\n' if a.modules else '').encode(),0o100644)]
    entries += [('modules/'+m.name,m.read_bytes(),0o100644) for m in a.modules]
    initrd=a.work/'initrd.gz';initrd.write_bytes(cpio(entries))
    results=[]
    for boot in [1,2]:
        command=[str(a.qemu),'-L',str(a.qemu_data),'-bios',str(a.bios),'-machine','q35','-accel','tcg','-cpu','max','-m','512','-smp','2','-display','none','-vga','none','-serial','stdio','-monitor','none','-nic','none','-no-reboot','-kernel',str(a.kernel),'-initrd',str(initrd),'-append','rdinit=/init console=ttyS0,115200 earlycon=uart8250,io,0x3f8 8250.nr_uarts=1 panic=-1','-drive',f'if=none,id=host,format=raw,file={host}','-device','virtio-blk-pci,drive=host']
        with (a.work/f'boot-{boot}.log').open('wb') as log:
            r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=90)
        text=(a.work/f'boot-{boot}.log').read_text(errors='replace')
        passed=r.returncode==0 and f'CONTAINER_PASS:system_ro:data_rw:boots={boot}' in text and 'CONTAINER_FAIL:' not in text and 'Kernel panic' not in text
        results.append({'boot':boot,'passed':passed,'exit_code':r.returncode})
        if not passed:break
    # Failure path must not fall through to a successful boot when payload is absent.
    missingfs=fs('missing-image-host',64<<20,{'CONTAINER-TEST.txt':'GBRUNCH FILE-ONLY FIXTURE\n'})
    missing=a.work/'missing-image.raw';gpt_image(missing,[('GBRUNCH',missingfs)])
    negative_command=[arg.replace(f'file={host}',f'file={missing}') for arg in command]
    with (a.work/'missing-image.log').open('wb') as log:
        negative=subprocess.run(negative_command,stdout=log,stderr=subprocess.STDOUT,timeout=90)
    text=(a.work/'missing-image.log').read_text(errors='replace')
    missing_refused=negative.returncode==0 and 'CONTAINER_FAIL:image_missing' in text and 'CONTAINER_PASS:' not in text
    report={'scope':'kernel + ext4 host + nested GPT + read-only system fixture + persistent writable data fixture; no Android, EFI or physical laptop validation','kernel_sha256':hashlib.file_digest(a.kernel.open('rb'),'sha256').hexdigest(),'outer_partitions':1,'nested_partitions':2,'physical_devices_attached':False,'results':results,'missing_image_refused':missing_refused,'passed':len(results)==2 and all(r['passed'] for r in results) and missing_refused}
    if a.debugfs and report['passed']:
        from readback import verify
        report['readback']=verify(a.work,a.debugfs)
    (a.work/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['passed'] else 1)
if __name__=='__main__':main()
