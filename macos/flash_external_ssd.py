#!/usr/bin/env python3
"""macOS external-SSD flasher. Streams a locally built image; no OS download."""
import argparse,gzip,hashlib,os,pathlib,plistlib,re,struct,subprocess,sys,time,zlib
BLOCK=4<<20

def command(args,**kw):return subprocess.run(args,check=True,**kw)
def plist(args):return plistlib.loads(subprocess.check_output(args))
def disk_info(device):return plist(['/usr/sbin/diskutil','info','-plist',device])
def check_target(info,image_bytes):
    if not re.fullmatch(r'disk\d+',str(info.get('DeviceIdentifier',''))):raise ValueError('Select a whole disk, not a partition')
    if info.get('WholeDisk') is not True or info.get('Internal') is not False or info.get('VirtualOrPhysical')!='Physical':raise ValueError('Target must be an external physical whole disk')
    if info.get('DeviceBlockSize')!=512:raise ValueError('This image requires 512-byte logical sectors')
    if int(info.get('TotalSize',0))<image_bytes:raise ValueError('SSD is smaller than the uncompressed image')
    if info.get('MediaReadOnly') or info.get('Writable') is False:raise ValueError('SSD is read-only')
    if not info.get('DeviceTreePath'):raise ValueError('Cannot establish the SSD connection identity')
    return {k:info.get(k) for k in ('DeviceIdentifier','DeviceTreePath','TotalSize','DeviceBlockSize','MediaName')}

def validate_gpt(first,last,size):
    if size%512 or first[512:520]!=b'EFI PART':raise ValueError('Not a complete GPT disk image')
    def header(data):
        if data[:8]!=b'EFI PART':raise ValueError('GPT header missing')
        n=struct.unpack_from('<I',data,12)[0]
        if n!=92:raise ValueError('Unexpected GPT header size')
        b=bytearray(data[:n]);expected=struct.unpack_from('<I',b,16)[0];struct.pack_into('<I',b,16,0)
        if zlib.crc32(b)!=expected:raise ValueError('GPT header CRC failed')
        return struct.unpack_from('<QQ',data,24)
    current,backup=header(first[512:1024]);h=first[512:1024]
    if current!=1 or backup!=size//512-1:raise ValueError('Image length does not match GPT')
    tlba,count,esz,crc=struct.unpack_from('<QIII',h,72)
    if tlba!=2 or count!=128 or esz!=128:raise ValueError('Unexpected recovery partition table')
    table=first[tlba*512:tlba*512+count*esz]
    if zlib.crc32(table)!=crc:raise ValueError('Partition-table CRC failed')
    bh=last[-512:];bc,bo=header(bh)
    if bc!=backup or bo!=1 or bh[56:72]!=h[56:72]:raise ValueError('Backup GPT does not match')
    btable=last[-33*512:-512]
    if btable!=table:raise ValueError('Backup partition table does not match')
    names=set();regions=[]
    for i in range(count):
        e=table[i*esz:(i+1)*esz]
        if not any(e[:16]):continue
        name=e[56:128].decode('utf-16le').rstrip('\0');a,b=struct.unpack_from('<QQ',e,32)
        if name in names or a<34 or a>b or b>=backup-32:raise ValueError('Invalid or duplicate partition entry')
        names.add(name);regions.append((a,b))
    regions.sort()
    if any(a[1]>=b[0] for a,b in zip(regions,regions[1:])):raise ValueError('Overlapping partitions')
    if not {'userdata','super','GBRUNCH','GBVENDOR','GBLOG','EFI-SYSTEM'}<=names:raise ValueError('Not an assembled GBRUNCH external OS image; official recovery alone or toolbox ISO cannot be flashed by this script')
    return len(names)

def inspect_image(path,expected):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(BLOCK):digest.update(b)
    if digest.hexdigest()!=expected.lower():raise ValueError('Input file SHA256 does not match the build checksum')
    opener=gzip.open if path.name.endswith('.gz') else open
    rawhash=hashlib.sha256();size=0;first=bytearray();last=bytearray()
    print('Checking the entire image without unpacking it...',flush=True)
    with opener(path,'rb') as f:
        while b:=f.read(BLOCK):
            rawhash.update(b);size+=len(b)
            if len(first)<1<<20:first.extend(b[:(1<<20)-len(first)])
            last.extend(b)
            if len(last)>1<<20:del last[:len(last)-(1<<20)]
    partitions=validate_gpt(bytes(first),bytes(last),size)
    return size,rawhash.hexdigest(),partitions

def source_physical_disks(image):
    # Resolve the input filesystem, including APFS containers, before unmounting.
    rows=subprocess.check_output(['/bin/df','-P',str(image)],text=True).splitlines()
    device=rows[-1].split()[0]
    if not re.fullmatch(r'/dev/disk\d+(?:s\d+)*',device):raise ValueError('Place the image on a local Mac disk before flashing')
    info=disk_info(device);parent=info.get('ParentWholeDisk') or info.get('DeviceIdentifier')
    whole=disk_info('/dev/'+parent)
    if whole.get('VirtualOrPhysical')=='Physical':return {whole['DeviceIdentifier']}
    container=info.get('APFSContainerReference') or parent
    apfs=plist(['/usr/sbin/diskutil','apfs','list','-plist'])
    for item in apfs.get('Containers',[]):
        if item.get('ContainerReference')==container:
            result=set()
            for store in item.get('PhysicalStores',[]):
                record=disk_info('/dev/'+store['DeviceIdentifier']);p=record.get('ParentWholeDisk') or record['DeviceIdentifier'];physical=disk_info('/dev/'+p)
                if physical.get('VirtualOrPhysical')!='Physical':raise ValueError('Cannot resolve image storage to a physical disk')
                result.add(physical['DeviceIdentifier'])
            if result:return result
    raise ValueError('Cannot establish where the input image is stored; refusing to unmount a possible source disk')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',type=pathlib.Path,required=True);p.add_argument('--disk',required=True);p.add_argument('--sha256',help='Defaults to first SHA256 in IMAGE.sha256');a=p.parse_args()
    if sys.platform!='darwin':p.error('This flasher runs on macOS only')
    if not re.fullmatch(r'/dev/disk\d+',a.disk):p.error('Use /dev/diskN for the external whole disk')
    image=a.image.expanduser().resolve()
    if not image.is_file():p.error('Locally built image file not found')
    expected=a.sha256
    if not expected:
        side=pathlib.Path(str(image)+'.sha256')
        if not side.is_file():p.error('Build checksum missing: supply --sha256 or IMAGE.sha256')
        lines=[x for x in side.read_text().splitlines() if x.strip()]
        if len(lines)!=1:p.error('Checksum file must contain exactly one record')
        expected=lines[0].split()[0]
    if not re.fullmatch(r'[0-9a-fA-F]{64}',expected):p.error('Invalid SHA256')
    before=image.stat();fingerprint=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
    size,rawhash,partitions=inspect_image(image,expected)
    info=disk_info(a.disk);identity=check_target(info,size)
    if info['DeviceIdentifier'] in source_physical_disks(pathlib.Path('/')):raise ValueError('Target contains the running macOS system; refusing to erase it')
    if info['DeviceIdentifier'] in source_physical_disks(image):raise ValueError('The input image is on the SSD you selected. Copy it to the Mac first')
    print(f"\nERASE ENTIRE EXTERNAL SSD: {a.disk}\nModel: {info.get('MediaName',info.get('IORegistryEntryName','unknown'))}\nCapacity: {info['TotalSize']/1e9:.1f} GB\nImage: {size/1e9:.1f} GB, {partitions} traditional partitions\nEvery existing partition and file on this SSD will be overwritten.")
    phrase='ERASE '+a.disk
    if input(f'Type {phrase} to continue: ').strip()!=phrase:print('Cancelled; no disk writes.');return
    command(['/usr/bin/sudo','-v'])
    command(['/usr/sbin/diskutil','unmountDisk',a.disk])
    if check_target(disk_info(a.disk),size)!=identity:raise ValueError('Disk identity changed after unmounting')
    now=image.stat()
    if (now.st_dev,now.st_ino,now.st_size,now.st_mtime_ns)!=fingerprint:raise ValueError('Image changed during preflight')
    raw='/dev/r'+info['DeviceIdentifier'];opener=gzip.open if image.name.endswith('.gz') else open
    proc=subprocess.Popen(['/usr/bin/sudo','/bin/dd','of='+raw,'bs=4m'],stdin=subprocess.PIPE)
    sent=0;written_hash=hashlib.sha256();last=0
    try:
        with opener(image,'rb') as f:
            while b:=f.read(BLOCK):
                proc.stdin.write(b);sent+=len(b);written_hash.update(b)
                if time.monotonic()-last>2:print(f'Writing: {sent/(1<<30):.1f} / {size/(1<<30):.1f} GiB',flush=True);last=time.monotonic()
        proc.stdin.close()
        if proc.wait()!=0 or sent!=size or written_hash.hexdigest()!=rawhash:raise ValueError('Write failed or input changed; do not boot this partial image')
    except BaseException:
        proc.terminate();proc.wait();raise
    command(['/bin/sync']);command(['/usr/sbin/diskutil','unmountDisk',a.disk])
    if check_target(disk_info(a.disk),size)!=identity:raise ValueError('Disk identity changed before verification')
    print('Reading the written image back for SHA256 verification...',flush=True)
    proc=subprocess.Popen(['/usr/bin/sudo','/bin/dd','if='+raw,'bs=4m','count='+str((size+BLOCK-1)//BLOCK)],stdout=subprocess.PIPE)
    digest=hashlib.sha256();left=size
    try:
        while b:=proc.stdout.read(BLOCK):
            take=min(left,len(b));digest.update(b[:take]);left-=take
        if proc.wait()!=0 or left or digest.hexdigest()!=rawhash:raise ValueError('SSD readback verification FAILED; do not boot this drive')
    except BaseException:
        proc.terminate();proc.wait();raise
    command(['/usr/sbin/diskutil','eject',a.disk])
    print('Verified and ejected. Connect to HP, keep Secure Boot disabled, then Esc -> F9 -> external UEFI. Select the HP Googlebook entry.')
if __name__=='__main__':
    try:main()
    except (Exception,KeyboardInterrupt) as e:print('\nSTOPPED: '+str(e)+'\nNo successful flash is claimed. Preserve the image; do not initialize or repair the SSD blindly.',file=sys.stderr);sys.exit(1)
