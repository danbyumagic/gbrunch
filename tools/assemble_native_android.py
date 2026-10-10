#!/usr/bin/env python3
"""Assemble a local Google recovery view using an isolated Linux build-tool VM.

Only new regular output files are accepted. Proprietary recovery and generated
vendor/ramdisk stay local. Boot eligibility is specified by validated kit assets.
"""
import argparse,gzip,hashlib,json,os,pathlib,shutil,stat,struct,subprocess,tempfile,urllib.request,uuid,zipfile,zlib
from inspect_recovery import gpt,decompress,align,u32
from assemble_external_lab import URL,ZIP_HASH,RAW_HASH,sha

def run(*args,**kwargs):return subprocess.run([str(a) for a in args],check=True,**kwargs)

def write_image(view,source,offset):
    # qemu-io's command parser does not safely accept arbitrary path spaces.
    # A short owned symlink avoids copying large local vendor/compat images.
    with tempfile.TemporaryDirectory(prefix='gbrunch-io-',dir='/tmp') as td:
        alias=pathlib.Path(td)/'payload';alias.symlink_to(source.resolve())
        run('qemu-io','-f','qcow2','-c',f'write -s {alias} {offset} {source.stat().st_size}',view)

def entry(name,data,mode,inode):
    n=name.encode()+b'\0';fields=[inode,mode,0,0,1,0,len(data),0,0,0,0,len(n),0]
    b=b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n
    return b+bytes(-len(b)%4)+data+bytes(-len(data)%4)

def original_boot_parts(blobs):
    b=blobs['boot_a'];assert b[:8]==b'ANDROID!' and u32(b,40)==4
    kernel=b[4096:4096+u32(b,8)]
    ib=blobs['init_boot_a'];assert ib[:8]==b'ANDROID!' and u32(ib,40)==4
    start=4096+align(u32(ib,8),4096);generic=decompress(ib[start:start+u32(ib,12)])
    vb=blobs['vendor_boot_a'];assert vb[:8]==b'VNDRBOOT' and u32(vb,8)==4
    page=u32(vb,12);start=align(u32(vb,2096),page)
    table=start+align(u32(vb,24),page)+align(u32(vb,2100),page)
    es=u32(vb,2120);fragments=[]
    for i in [0,2]:
        size,offset=struct.unpack_from('<II',vb,table+i*es)
        fragments.append(decompress(vb[start+offset:start+offset+size]))
    return kernel,b''.join(fragments)+generic

def recovery(a):
    if a.recovery_raw:
        base=a.recovery_raw.resolve()
    else:
        z=a.recovery_zip.resolve() if a.recovery_zip else a.cache/'ruby-recovery.zip'
        if not z.exists():
            part=z.with_suffix('.download');print('Downloading official recovery:',URL,flush=True)
            urllib.request.urlretrieve(URL,part);part.rename(z)
        if sha(z)!=ZIP_HASH:raise ValueError('Official ZIP hash mismatch')
        base=a.cache/'ruby-recovery.raw'
        if not base.exists():
            part=base.with_suffix('.extracting')
            with zipfile.ZipFile(z) as archive:
                candidates=[v for v in archive.infolist() if v.file_size==19069493760]
                assert len(candidates)==1,'Unexpected official recovery ZIP'
                with archive.open(candidates[0]) as f,part.open('xb') as out:
                    for b in iter(lambda:f.read(1<<20),b''):
                        if b.strip(b'\0'):out.write(b)
                        else:out.seek(len(b),1)
                    out.truncate()
            part.rename(base)
    print('Verifying official raw recovery (~19 GB read)...',flush=True)
    assert base.is_file() and not str(base).startswith('/dev/')
    if sha(base)!=RAW_HASH:raise ValueError('Official raw recovery hash mismatch')
    return base

def main():
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_mutually_exclusive_group(required=True)
    s.add_argument('--download',action='store_true');s.add_argument('--recovery-zip',type=pathlib.Path);s.add_argument('--recovery-raw',type=pathlib.Path)
    p.add_argument('--output',type=pathlib.Path,required=True)
    p.add_argument('--cache',type=pathlib.Path,default=pathlib.Path('google-recovery-cache'))
    p.add_argument('--assets',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parent)
    p.add_argument('--format',choices=['raw','qcow2'],default='raw')
    a=p.parse_args();out=a.output.absolute();a.cache=a.cache.resolve();assets=a.assets.resolve()
    if out.exists() or out.is_symlink() or str(out).startswith('/dev/') or not out.parent.is_dir():p.error('Output must be a NEW regular file in an existing directory.')
    for t in ['qemu-system-x86_64','qemu-img','qemu-io','mcopy','mformat','lz4']:
        if not shutil.which(t):p.error('Missing program: '+t+' (macOS: brew install qemu mtools lz4)')
    manifest=json.loads((assets/'native-assets.json').read_text())
    for n,h in manifest['files'].items():
        if sha(assets/n)!=h:raise ValueError('Asset hash mismatch: '+n)
    a.cache.mkdir(parents=True,exist_ok=True);base=recovery(a)
    with base.open('rb') as f:
        parts=gpt(f);by={v['name']:v for v in parts};f.seek(0);mbr=bytearray(f.read(512));header=bytearray(f.read(512))
        tlba,count,esz=struct.unpack_from('<QII',header,72);f.seek(tlba*512);table=bytearray(f.read(count*esz))
        blobs={}
        for n in ['boot_a','init_boot_a','vendor_boot_a','vbmeta_a']:
            f.seek(by[n]['offset']);blobs[n]=f.read(by[n]['bytes'])
    with tempfile.TemporaryDirectory(prefix='gbrunch-native-',dir=a.cache) as td:
        w=pathlib.Path(td);fat=w/'work.fat'
        with fat.open('xb') as f:f.truncate(1<<30)
        run('mformat','-i',fat,'-F','-T','2097152','::')
        marker=w/'GBRUNCH-BUILD-MARKER.txt';marker.write_text('GBRUNCH local build-tool work disk\n')
        run('mcopy','-i',fat,marker,'::/')
        print('Deriving vendor and matching modules in isolated Linux build VM...',flush=True)
        vm=['qemu-system-x86_64','-machine','q35','-accel','tcg','-cpu','qemu64','-m','1024','-smp','2',
            '-vga','none','-display','none','-serial','stdio','-monitor','none','-net','none','-no-reboot',
            '-kernel',assets/'tool-linux-kernel','-initrd',assets/'tool-initrd.gz',
            '-append','rdinit=/init console=ttyS0,115200 loglevel=6 panic=0 gbrunch.toolvm=1',
            '-drive',f'if=none,id=work,format=raw,file={fat}','-device','virtio-blk-pci,drive=work',
            '-drive',f'if=none,id=recovery,format=raw,readonly=on,file={base}','-device','virtio-blk-pci,drive=recovery']
        with out.with_name(out.name+'.build-vm.log').open('wb') as log:run(*vm,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=900)
        status=subprocess.check_output(['mcopy','-i',str(fat),'::/status.txt','-']).strip()
        assert status==b'0','Local build failed; inspect .build-vm.log'
        result=json.loads(subprocess.check_output(['mcopy','-i',str(fat),'::/result.json','-']))
        vendor=w/'vendor.erofs';run('mcopy','-i',fat,'::/vendor.erofs',vendor)
        assert sha(vendor)==result['vendor_sha256'] and vendor.stat().st_size==result['vendor_bytes']
        kernel,original_ramdisk=original_boot_parts(blobs)
        assert hashlib.sha256(kernel).hexdigest()==manifest['google_kernel_sha256']
        (w/'kernel').write_bytes(kernel)
        extra={};deps=[];aliases=[];modules=manifest['modules'];names={v['name']:v['file'] for v in modules}
        for v in modules:
            b=subprocess.check_output(['mcopy','-i',str(fat),'::/modules/'+v['file'],'-'])
            assert hashlib.sha256(b).hexdigest()==v['sha256']
            extra['lib/modules/'+v['file']]=(stat.S_IFREG|0o644,b)
            d=['/lib/modules/'+names[x.replace('-','_')] for x in v['depends']]
            deps.append('/lib/modules/'+v['file']+':'+((' '+' '.join(d)) if d else ''))
            aliases.extend('alias '+x+' '+v['name'] for x in v['aliases'])
        for v in manifest['firmware']:
            b=(assets/'firmware'/v['name']).read_bytes();assert hashlib.sha256(b).hexdigest()==v['sha256']
            extra['lib/firmware/'+v['name']]=(stat.S_IFREG|0o644,b)
        for n,b in [('modules.load','\n'.join(v['file'] for v in modules)),('modules.load.recovery','\n'.join(v['file'] for v in modules)),
                    ('modules.dep','\n'.join(deps)),('modules.alias','\n'.join(aliases)),('modules.softdep',''),('modules.options','')]:
            extra['lib/modules/'+n]=(stat.S_IFREG|0o644,(b+'\n').encode())
        extra['first_stage_ramdisk/fstab.android-desktop']=(stat.S_IFREG|0o644,(assets/'fstab.android-desktop').read_bytes())
        for n in ['lib','lib/modules','lib/firmware','lib/firmware/i915']:extra[n]=(stat.S_IFDIR|0o755,b'')
        overlay=b''.join(entry(n,b,m,970000+i) for i,(n,(m,b)) in enumerate(sorted(extra.items())))+entry('TRAILER!!!',b'',0,979999)
        rd=original_ramdisk+overlay
        (w/'initrd.gz').write_bytes(gzip.compress(rd,mtime=0))
        fat.unlink()  # All verified outputs are read; release the local VM scratch disk.
        vb=blobs['vbmeta_a'];vs=256+int.from_bytes(vb[12:20],'big')+int.from_bytes(vb[20:28],'big')
        cmd=manifest['cmdline'].replace('BOOT_GUID',by['boot_a']['guid']).replace('VBMETA_SIZE',str(vs)).replace('VBMETA_DIGEST',hashlib.sha256(vb[:vs]).hexdigest())
        (w/'grub.cfg').write_text((assets/'native-grub.cfg').read_text().replace('CMDLINE',cmd))
        esp=w/'esp.fat';shutil.copyfile(assets/'esp-template.fat',esp)
        for file,n in [(w/'kernel','kernel'),(w/'initrd.gz','initrd.gz'),(w/'grub.cfg','grub.cfg')]:run('mcopy','-o','-i',esp,file,'::/EFI/GBRUNCH/'+n)
        logfat=w/'logs.fat'
        with logfat.open('xb') as f:f.truncate(256<<20)
        run('mformat','-i',logfat,'-F','-T','524288','-v','GBRUNCH_LOG','::')
        marker=w/'GBRUNCH-NATIVE-LOGS.txt';marker.write_text('GBRUNCH independent Android diagnostic logs\n');run('mcopy','-i',logfat,marker,'::/')
        cursor=(base.stat().st_size+1048575)//1048576*1048576;appended=[]
        for n,file,guid in [('GBRUNCH',assets/'compat.ext4','4ab7c001'),('GBVENDOR',vendor,'4ab7c002'),('GBLOG',logfat,'4ab7c003')]:
            size=(file.stat().st_size+1048575)//1048576*1048576;start=cursor//512;end=(cursor+size)//512-1
            slot=next(i for i in range(count) if not any(table[i*esz:i*esz+16]))
            e=bytearray(esz);e[:16]=uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le;e[16:32]=uuid.UUID(guid+'-7400-4bab-b412-43cbd52b9fb1').bytes_le
            struct.pack_into('<QQQ',e,32,start,end,0);encoded=n.encode('utf-16le');e[56:56+len(encoded)]=encoded;table[slot*esz:(slot+1)*esz]=e
            appended.append({'name':n,'index':slot+1,'offset':cursor,'bytes':size,'file':str(file)});cursor+=size
        ts=(len(table)+511)//512;last=cursor//512+ts;struct.pack_into('<Q',header,32,last);struct.pack_into('<Q',header,48,cursor//512-1)
        struct.pack_into('<I',header,88,zlib.crc32(table));struct.pack_into('<I',header,16,0);struct.pack_into('<I',header,16,zlib.crc32(header[:92]))
        backup=bytearray(header);struct.pack_into('<QQ',backup,24,last,1);struct.pack_into('<Q',backup,72,last-ts);struct.pack_into('<I',backup,16,0);struct.pack_into('<I',backup,16,zlib.crc32(backup[:92]));struct.pack_into('<I',mbr,458,min(last,0xffffffff))
        view=w/'native.qcow2';run('qemu-img','create','-f','qcow2','-F','raw','-b',base,view,(last+1)*512)
        patches=[('mbr',0,mbr),('header',512,header),('table',tlba*512,table),('backup-table',(last-ts)*512,table),('backup-header',last*512,backup)]
        for n,pos,b in patches:
            f=w/(n+'.bin');f.write_bytes(b);write_image(view,f,pos)
        ef=next(v for v in parts if v['type_guid']=='c12a7328-f81f-11d2-ba4b-00a0c93ec93b');assert esp.stat().st_size<=ef['bytes']
        for pos,file in [(ef['offset'],esp)]+[(v['offset'],pathlib.Path(v['file'])) for v in appended]:
            if file==logfat:
                # New appended space reads as zero; skip empty FAT data clusters.
                with file.open('rb') as f:
                    i=0
                    for chunk in iter(lambda:f.read(1<<20),b''):
                        if chunk.strip(b'\0'):
                            tmp=w/'log-chunk.bin';tmp.write_bytes(chunk);write_image(view,tmp,pos+i*(1<<20))
                        i+=1
            else:write_image(view,file,pos)
        if a.format=='raw':run('qemu-img','convert','-f','qcow2','-O','raw','-S','64k',view,out)
        else:
            shutil.move(view,out)
            # Live USB persistence mount paths can change across reboots.
            # Keep the verified base reference relative to the finished view.
            run('qemu-img','rebase','-u','-f','qcow2','-F','raw',
                '-b',os.path.relpath(base,out.parent),out)
        for v in appended:v.pop('file')
        report={'scope':'local experimental Android image; HP interface not yet tested','physical_boot_enabled':manifest['physical_boot_enabled'],'original_raw_sha256':RAW_HASH,
                'system_preservation':'All original GPT records retained; EFI changed only in output; original super/system/vendor bytes untouched',
                'vendor':result,'appended_partitions':appended,'cmdline':cmd,'format':a.format,
                'userdata_encryption':'disabled for this experiment','output_sha256':sha(out),'distribution':'local use only; do not upload this image'}
        out.with_name(out.name+'.manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Prepared local experimental image:',out,flush=True)

if __name__=='__main__':main()
