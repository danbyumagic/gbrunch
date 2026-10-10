#!/usr/bin/env python3
"""Local, QEMU-only UEFI research image. Never accepts physical disk outputs.

Requires qemu-img, qemu-io, mcopy and lz4 in PATH and the adjacent asset kit.
Google partitions retain their exact extents and bytes, except the EFI partition
in the new image view. The original downloaded recovery is never written.
"""
import argparse, gzip, hashlib, json, pathlib, shutil, struct, subprocess
import tempfile, urllib.request, uuid, zipfile, zlib
from inspect_recovery import boot, gpt

URL='https://dl.google.com/device/recovery/ruby-user/16452207/recovery.zip'
ZIP_HASH='3c4dc7f636f29a1207e71d001fd2864aa20ce8354faecd2ef1ae47582b977f6c'
RAW_HASH='4f4490415d4db0721fa99ad10abd64b1b05c284b6c0e413907da948561de8c9e'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()

def run(*args): subprocess.run([str(x) for x in args],check=True)

def cpio_file(name,data,inode):
    n=name.encode()+b'\0'
    fields=[inode,0o100644,0,0,1,0,len(data),0,0,0,0,len(n),0]
    b=b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n
    b+=bytes(-len(b)%4);b+=data+bytes(-len(data)%4)
    n=b'TRAILER!!!\0';fields=[inode+1,0,0,0,1,0,0,0,0,0,0,len(n),0]
    t=b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n
    return b+t+bytes(-len(t)%4)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    src=p.add_mutually_exclusive_group(required=True)
    src.add_argument('--download',action='store_true');src.add_argument('--recovery-zip',type=pathlib.Path)
    src.add_argument('--recovery-raw',type=pathlib.Path)
    p.add_argument('--output',type=pathlib.Path,required=True)
    p.add_argument('--cache',type=pathlib.Path,default=pathlib.Path('google-recovery-cache'))
    p.add_argument('--assets',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parent)
    p.add_argument('--format',choices=['raw','qcow2'],default='raw')
    a=p.parse_args();out=a.output.absolute();assets=a.assets.resolve()
    if out.exists() or out.is_symlink() or str(out).startswith('/dev/'):
        p.error('Output must be a new regular file, never a device or existing path.')
    if not out.parent.is_dir():p.error('Output directory must already exist.')
    for t in ['qemu-img','qemu-io','mcopy','lz4']:
        if not shutil.which(t):p.error('Missing program: '+t)
    manifest=json.loads((assets/'manifest.json').read_text())
    for name,h in manifest['files'].items():
        if sha(assets/name)!=h:raise ValueError('Asset hash mismatch: '+name)
    a.cache.mkdir(parents=True,exist_ok=True)
    if a.recovery_raw:
        base=a.recovery_raw.resolve()
    else:
        z=a.recovery_zip.resolve() if a.recovery_zip else a.cache.resolve()/'ruby-recovery.zip'
        if not z.exists():
            tmp=z.with_suffix('.download')
            print('Downloading official recovery (~7.8 GB):',URL,flush=True)
            urllib.request.urlretrieve(URL,tmp);tmp.rename(z)
        if sha(z)!=ZIP_HASH:raise ValueError('Official recovery ZIP hash mismatch')
        base=a.cache.resolve()/'ruby-recovery.raw'
        if not base.exists():
            temporary=base.with_suffix('.extracting')
            with zipfile.ZipFile(z) as archive:
                candidates=[x for x in archive.infolist() if x.file_size==19069493760]
                if len(candidates)!=1:raise ValueError('Unexpected recovery ZIP layout')
                with archive.open(candidates[0]) as f,temporary.open('xb') as dest:
                    for b in iter(lambda:f.read(1<<20),b''):
                        if b.strip(b'\0'):dest.write(b)
                        else:dest.seek(len(b),1)
                    dest.truncate()
            temporary.rename(base)
    print('Verifying original raw recovery; this reads ~19 GB.',flush=True)
    if sha(base)!=RAW_HASH:raise ValueError('Official recovery raw hash mismatch')
    with base.open('rb') as f:
        parts=gpt(f);byname={x['name']:x for x in parts}
        f.seek(0);mbr=bytearray(f.read(512));header=bytearray(f.read(512))
        tlba,count,esz=struct.unpack_from('<QII',header,72)
        f.seek(tlba*512);table=bytearray(f.read(count*esz))
        blobs={}
        for name in ['boot_a','init_boot_a','vendor_boot_a','vbmeta_a']:
            x=byname[name];f.seek(x['offset']);blobs[name]=f.read(x['bytes'])
    with tempfile.TemporaryDirectory(prefix='gbrunch-lab-') as td:
        w=pathlib.Path(td)
        for name in ['boot_a','init_boot_a','vendor_boot_a']:boot(blobs[name],name,w)
        initrd=(w/'vendor_boot_a/fragment-0-platform.cpio').read_bytes()
        initrd+=(w/'vendor_boot_a/fragment-2-dlkm.cpio').read_bytes()
        initrd+=(w/'init_boot_a/ramdisk.cpio').read_bytes()
        initrd+=cpio_file('lib/modules/modules.load',b'# GBRUNCH: board-specific early loads suppressed\n',900000)
        initrd+=cpio_file('first_stage_ramdisk/fstab.android-desktop',(assets/'fstab.android-desktop').read_bytes(),900002)
        (w/'initrd.gz').write_bytes(gzip.compress(initrd,mtime=0))
        vb=blobs['vbmeta_a'];size=256+int.from_bytes(vb[12:20],'big')+int.from_bytes(vb[20:28],'big')
        cmd=' '.join(['rdinit=/init','root=/dev/ram0','console=ttyS0,115200',
            'earlycon=uart8250,io,0x3f8,115200','8250.nr_uarts=4','panic=0','loglevel=8',
            'ignore_loglevel','printk.time=1','printk.devkmsg=on','log_buf_len=8M','initcall_debug',
            'androidboot.init_log_level=debug','androidboot.hardware=android-desktop',
            'androidboot.hardware.platform=android-desktop','androidboot.slot_suffix=_a',
            'androidboot.force_normal_boot=1','androidboot.boot_part_uuid='+byname['boot_a']['guid'],
            'androidboot.vbmeta.size='+str(size),'androidboot.vbmeta.hash_alg=sha256',
            'androidboot.vbmeta.digest='+hashlib.sha256(vb[:size]).hexdigest(),
            'androidboot.vbmeta.device_state=unlocked','androidboot.verifiedbootstate=orange',
            'androidboot.veritymode=enforcing','androidboot.hypervisor.protected_vm.supported=0',
            'androidboot.vendor.apex.com.android.hardware.keymint.strongbox.desktop=none',
            'androidboot.init_rc=/oem/init.gbrunch.rc'])
        cfg='''set timeout=5
set default=0
serial --unit=0 --speed=115200
terminal_output console serial
menuentry 'GBRUNCH Android research boot (QEMU only)' {
 insmod smbios
 smbios --type=1 --get-string=4 --set=system_vendor
 if [ "$system_vendor" = "QEMU" ]; then
  linux /EFI/GBRUNCH/kernel CMDLINE
  initrd /EFI/GBRUNCH/initrd.gz
 else
  echo 'Use the separate HP diagnostic image on physical hardware.'
  echo 'Android graphics, security and firmware audit remain incomplete.'
  sleep 15
 fi
}
menuentry 'UEFI firmware settings' { fwsetup }
'''.replace('CMDLINE',cmd)
        (w/'grub.cfg').write_text(cfg)
        fat=w/'esp.fat';shutil.copyfile(assets/'esp-template.fat',fat)
        for file,dest in [(w/'boot_a/kernel','kernel'),(w/'initrd.gz','initrd.gz'),(w/'grub.cfg','grub.cfg')]:
            run('mcopy','-o','-i',fat,file,'::/EFI/GBRUNCH/'+dest)
        # Keep the original EFI partition extent and replace only its view bytes.
        esp=byname['EFI-SYSTEM'] if 'EFI-SYSTEM' in byname else next(x for x in parts if x['type_guid']=='c12a7328-f81f-11d2-ba4b-00a0c93ec93b')
        if fat.stat().st_size>esp['bytes']:raise ValueError('EFI template exceeds original EFI partition')
        compat=assets/'compat.ext4'
        start=(base.stat().st_size+1048575)//1048576*2048
        end=start+compat.stat().st_size//512-1;ts=(len(table)+511)//512;last=end+ts+1
        slot=next(i for i in range(count) if not any(table[i*esz:i*esz+16]))
        e=bytearray(esz);e[:16]=uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le
        e[16:32]=uuid.UUID('4ab7c001-7400-4bab-b412-43cbd52b9fb1').bytes_le
        struct.pack_into('<QQQ',e,32,start,end,0);e[56:70]='GBRUNCH'.encode('utf-16le')
        table[slot*esz:(slot+1)*esz]=e
        struct.pack_into('<Q',header,32,last);struct.pack_into('<Q',header,48,end)
        struct.pack_into('<I',header,88,zlib.crc32(table));struct.pack_into('<I',header,16,0)
        struct.pack_into('<I',header,16,zlib.crc32(header[:struct.unpack_from('<I',header,12)[0]]))
        bh=bytearray(header);struct.pack_into('<QQ',bh,24,last,1);struct.pack_into('<Q',bh,72,last-ts)
        struct.pack_into('<I',bh,16,0);struct.pack_into('<I',bh,16,zlib.crc32(bh[:struct.unpack_from('<I',bh,12)[0]]))
        struct.pack_into('<I',mbr,458,min(last,0xffffffff))
        view=w/'view.qcow2'
        run('qemu-img','create','-f','qcow2','-F','raw','-b',base,view,(last+1)*512)
        for name,offset,b in [('mbr',0,mbr),('header',512,header),('table',tlba*512,table),('backup-table',(last-ts)*512,table),('backup-header',last*512,bh)]:
            patch=w/(name+'.bin');patch.write_bytes(b)
            run('qemu-io','-f','qcow2','-c',f'write -s {patch} {offset} {len(b)}',view)
        for file,offset in [(compat,start*512),(fat,esp['offset'])]:
            # qemu-io command filenames use an owned space-free temporary copy.
            patch=w/(file.name+'.patch');shutil.copyfile(file,patch)
            run('qemu-io','-f','qcow2','-c',f'write -s {patch} {offset} {patch.stat().st_size}',view)
        if a.format=='raw':run('qemu-img','convert','-f','qcow2','-O','raw',view,out)
        else:shutil.copyfile(view,out)
        out.with_name(out.name+'.manifest.json').write_text(json.dumps({
            'scope':'QEMU-only experimental UEFI image; no working desktop',
            'original_recovery':str(base),'original_raw_sha256':RAW_HASH,
            'preservation':'All original GPT extents/GUIDs retained; original system/vendor/super bytes untouched. EFI replaced in output view only.',
            'output_format':a.format,'output_sha256':sha(out),'cmdline':cmd,
            'boot_gate':'GRUB SMBIOS manufacturer must equal QEMU; physical HP uses separate diagnostics',
            'userdata_encryption':'Disabled in VM diagnostic fstab only',
            'remaining':'Graphics, software-security VINTF/SELinux, bare-metal firmware audit and HP drivers'
        },indent=2)+'\n')
    print('Prepared research image:',out,flush=True)

if __name__=='__main__':main()
