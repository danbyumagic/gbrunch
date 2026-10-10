#!/usr/bin/env python3
"""Work-only UEFI/USB integration view; locally generated Google data stays local.

Does not enable physical Android boot or accept physical disk outputs. The
hardware handoff still needs a portable local assembler and log retrieval.
"""
import hashlib,json,os,pathlib,shutil,struct,subprocess,uuid,zlib

R=pathlib.Path(__file__).resolve().parents[1]
O=R/'build/native-android-gpu'
L=R/'tools/local'
env=os.environ.copy()
env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
def run(*args):subprocess.run([str(a) for a in args],env=env,check=True)

def main():
    backing=R/'build/vendor-view-native/recovery-vendor-view.qcow2'
    out=O/'uefi-usb-view.qcow2'
    assert not out.exists() and not out.is_symlink(), 'Refusing existing output'
    vb=(R/'extracted/ruby/vbmeta_a.img').read_bytes()
    size=256+int.from_bytes(vb[12:20],'big')+int.from_bytes(vb[20:28],'big')
    parts=json.loads((R/'extracted/ruby/gpt.json').read_text())
    boot=next(p for p in parts if p['name']=='boot_a')
    esp=next(p for p in parts if p['type_guid']=='c12a7328-f81f-11d2-ba4b-00a0c93ec93b')
    cmd=' '.join(['rdinit=/init','root=/dev/ram0','console=ttyS0,115200',
        'earlycon=uart8250,io,0x3f8,115200','8250.nr_uarts=4','panic=0','loglevel=8',
        'ignore_loglevel','printk.time=1','printk.devkmsg=on','log_buf_len=8M',
        'drm.debug=0x1e','efi_pstore.pstore_disable=1',
        'androidboot.init_log_level=debug','androidboot.hardware=android-desktop',
        'androidboot.hardware.platform=android-desktop','androidboot.slot_suffix=_a',
        'androidboot.force_normal_boot=1','androidboot.boot_part_uuid='+boot['guid'],
        'androidboot.vbmeta.size='+str(size),'androidboot.vbmeta.hash_alg=sha256',
        'androidboot.vbmeta.digest='+hashlib.sha256(vb[:size]).hexdigest(),
        'androidboot.vbmeta.device_state=unlocked','androidboot.verifiedbootstate=orange',
        'androidboot.veritymode=enforcing','androidboot.hypervisor.protected_vm.supported=0',
        'androidboot.vendor.apex.com.android.hardware.keymint.strongbox.desktop=none',
        'androidboot.init_rc=/oem/init.gbrunch.rc'])
    cfg='''set timeout=2
set default=0
serial --unit=0 --speed=115200
terminal_output console serial
menuentry 'GBRUNCH integrated Xe Android experiment (Work VM)' {
 insmod smbios
 smbios --type=1 --get-string=4 --set=system_vendor
 if [ "$system_vendor" = "QEMU" ]; then
  linux /EFI/GBRUNCH/kernel CMDLINE
  initrd /EFI/GBRUNCH/initrd.gz
 else
  echo 'Physical Android image assembly and logger validation remain unfinished.'
  sleep 15
 fi
}
menuentry 'UEFI firmware settings' { fwsetup }
'''.replace('CMDLINE',cmd)
    (O/'grub.cfg').write_text(cfg)
    fat=O/'esp.fat'
    shutil.copyfile(R/'build/external-lab-assets/esp-template.fat',fat)
    assert fat.stat().st_size<=esp['bytes']
    for p,n in [(R/'extracted/ruby/boot_a/kernel','kernel'),(O/'initrd.gz','initrd.gz'),(O/'grub.cfg','grub.cfg')]:
        run(L/'usr/bin/mcopy','-o','-i',fat,p,'::/EFI/GBRUNCH/'+n)
    # Append independent log storage; retain all original GPT entries/extents.
    prefix=O/'parent-prefix.bin'
    run(R/'build/qemu11/qemu-img','dd','-f','qcow2','if='+str(backing),'of='+str(prefix),'bs=512','count=34')
    data=prefix.read_bytes();mbr=bytearray(data[:512]);header=bytearray(data[512:1024])
    tlba,count,esz=struct.unpack_from('<QII',header,72);table=bytearray(data[tlba*512:tlba*512+count*esz])
    assert zlib.crc32(table)==struct.unpack_from('<I',header,88)[0]
    info=json.loads(subprocess.check_output([str(R/'build/qemu11/qemu-img'),'info','--output=json',str(backing)]))
    start=(info['virtual-size']+1048575)//1048576*2048;end=start+524288-1
    ts=(len(table)+511)//512;last=end+ts+1
    slot=next(i for i in range(count) if not any(table[i*esz:i*esz+16]))
    ent=bytearray(esz);ent[:16]=uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le
    ent[16:32]=uuid.UUID('4ab7c003-7400-4bab-b412-43cbd52b9fb1').bytes_le
    struct.pack_into('<QQQ',ent,32,start,end,0);ent[56:66]='GBLOG'.encode('utf-16le')
    table[slot*esz:(slot+1)*esz]=ent
    struct.pack_into('<Q',header,32,last);struct.pack_into('<Q',header,48,end)
    struct.pack_into('<I',header,88,zlib.crc32(table));struct.pack_into('<I',header,16,0);struct.pack_into('<I',header,16,zlib.crc32(header[:92]))
    backup=bytearray(header);struct.pack_into('<QQ',backup,24,last,1);struct.pack_into('<Q',backup,72,last-ts)
    struct.pack_into('<I',backup,16,0);struct.pack_into('<I',backup,16,zlib.crc32(backup[:92]));struct.pack_into('<I',mbr,458,min(last,0xffffffff))
    logfat=O/'log-template.fat'
    with logfat.open('wb') as f:f.truncate(256*1024*1024)
    run(L/'usr/sbin/mkfs.fat','-F','32','-i','47424c47','-n','GBRUNCH_LOG',logfat)
    marker=O/'GBRUNCH-NATIVE-LOGS.txt';marker.write_text('GBRUNCH independent Android diagnostic logs\n')
    run(L/'usr/bin/mcopy','-o','-i',logfat,marker,'::/GBRUNCH-NATIVE-LOGS.txt')
    run(R/'build/qemu11/qemu-img','create','-f','qcow2','-F','qcow2','-b',backing,out,(last+1)*512)
    for name,pos,blob in [('mbr',0,mbr),('header',512,header),('table',tlba*512,table),('backup-table',(last-ts)*512,table),('backup-header',last*512,backup)]:
        file=O/('log-gpt-'+name+'.bin');file.write_bytes(blob)
        run(R/'build/qemu11/qemu-io','-f','qcow2','-c',f'write -s {file} {pos} {len(blob)}',out)
    with logfat.open('rb') as f:
        for i in range(256):
            chunk=f.read(1048576)
            if chunk.strip(b'\0'):
                tmp=O/'log-fat-chunk.bin';tmp.write_bytes(chunk)
                run(R/'build/qemu11/qemu-io','-f','qcow2','-c',f'write -s {tmp} {start*512+i*1048576} {len(chunk)}',out)

    run(R/'build/qemu11/qemu-io','-f','qcow2','-c',f'write -s {fat} {esp["offset"]} {fat.stat().st_size}',out)
    result={'scope':'local-only QEMU UEFI integration; no proprietary output distribution',
            'backing':str(backing),'output':str(out),'changed_partition':'EFI only in this child',
            'vendor':'independent GBVENDOR in parent; original vendor remains untouched',
            'system':'original recovery bytes/AVB unchanged','cmdline':cmd,
            'initrd_sha256':hashlib.sha256((O/'initrd.gz').read_bytes()).hexdigest(),
            'physical_android_enabled':False,'log_partition':{'index':slot+1,'offset':start*512,'bytes':256*1024*1024,'guid':'4ab7c003-7400-4bab-b412-43cbd52b9fb1'}}
    (O/'uefi-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
