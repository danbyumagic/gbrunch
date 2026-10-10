#!/usr/bin/env python3
"""Run the isolated Linux filesystem tool against one identified external SSD.

Inspect exposes that drive read-only. Diagnose replays its journal only in a
local overlay over a read-only backing device. Expand is allowed only for this project's
validated userdata/GPT identity. No internal disk is passed into QEMU.
"""
import argparse,hashlib,json,os,pathlib,plistlib,re,shutil,subprocess,sys,zipfile

def sha256_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def validate_disk_identity(meta, disk):
    """Fail closed using diskutil's macOS plist fields."""
    if not (meta.get('Internal') is False and meta.get('WholeDisk') is True):
        raise ValueError('Refusing anything except an external whole disk.')
    if meta.get('DeviceNode') != disk or meta.get('DeviceIdentifier') != disk[len('/dev/'):]:
        raise ValueError('Disk identity does not match the requested device.')
    if meta.get('VirtualOrPhysical') != 'Physical' or meta.get('SystemImage') is True:
        raise ValueError('Physical external SSD required.')
    if meta.get('DeviceBlockSize') != 512:
        raise ValueError('Only 512-byte logical-sector drives are validated.')
    if not isinstance(meta.get('TotalSize'), int) or meta['TotalSize'] < (90 << 30):
        raise ValueError('Drive too small for the planned 64GiB userdata and OS.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--disk',required=True);p.add_argument('--action',choices=['inspect','diagnose','expand','reset'],default='inspect')
    p.add_argument('--qemu',required=True);p.add_argument('--mcopy',required=True);p.add_argument('--mformat',required=True)
    p.add_argument('--qemu-img',help='Required for diagnose; creates a temporary local overlay.')
    p.add_argument('--work',type=pathlib.Path,required=True)
    a=p.parse_args()
    if sys.platform!='darwin':p.error('This wrapper requires macOS diskutil identity checks.')
    if os.geteuid()!=0:p.error('Use sudo to access the external raw disk.')
    if not re.fullmatch(r'/dev/disk[0-9]+',a.disk):p.error('Supply a whole disk identifier, e.g. /dev/disk21.')
    meta=plistlib.loads(subprocess.check_output(['diskutil','info','-plist',a.disk]))
    try:validate_disk_identity(meta,a.disk)
    except ValueError as exc:p.error(str(exc))
    assets=pathlib.Path(__file__).resolve().parent
    manifest=json.loads((assets/'asset-hashes.json').read_text())
    for name,h in manifest.items():
        actual=sha256_file(assets/name)
        if actual!=h:p.error('Asset hash mismatch: '+name)
    if a.action=='diagnose' and not a.qemu_img:p.error('Diagnose requires --qemu-img.')
    work=a.work.absolute()
    if work.exists() or work.is_symlink():p.error('Work directory must be new; preserve each earlier report separately.')
    work.mkdir(parents=True)
    (work/'disk-identity.plist').write_bytes(plistlib.dumps(meta))
    (work/'GBRUNCH-USERDATA-MARKER.txt').write_text('GBRUNCH isolated userdata maintenance\n')
    (work/'request.json').write_text(json.dumps({'action':a.action,'gib':64}))
    fat=work/'work.fat'
    with fat.open('xb') as f:f.truncate(256<<20)
    subprocess.run([a.mformat,'-i',str(fat),'-F','-T','524288','::'],check=True)
    for name in ['GBRUNCH-USERDATA-MARKER.txt','request.json']:
        subprocess.run([a.mcopy,'-i',str(fat),str(work/name),'::/'],check=True)
    subprocess.run(['diskutil','unmountDisk',a.disk],check=True)
    raw=a.disk.replace('/dev/disk','/dev/rdisk')
    drive=f'if=none,id=disk,format=raw,file={raw}'
    if a.action=='inspect':drive+=',readonly=on'
    cmd=[a.qemu,'-machine','q35','-accel','tcg','-cpu','qemu64','-m','1024','-smp','2','-display','none','-vga','none',
         '-serial','stdio','-monitor','none','-net','none','-no-reboot','-kernel',str(assets/'linux-kernel'),
         '-initrd',str(assets/'initrd.gz'),'-append','rdinit=/init console=ttyS0,115200 loglevel=5 panic=0 gbrunch.userdata_vm=1',
         '-drive',f'if=none,id=work,format=raw,file={str(fat).replace(",",",,")}','-device','virtio-blk-pci,drive=work',
         '-drive',drive,'-device','virtio-blk-pci,drive=disk']
    if a.action=='diagnose':
        cmd[cmd.index('-append')+1]+=' gbrunch.userdata_overlay=1'
        overlay=work/'diagnostic-overlay.qcow2'
        subprocess.run([a.qemu_img,'create','-f','qcow2',str(overlay),str(meta['TotalSize'])],check=True)
        # Explicit read-only raw backing: journal writes can only land in the
        # local qcow2 overlay. The selected physical SSD cannot receive writes.
        i=cmd.index('-drive',cmd.index('-drive')+1)
        cmd[i:i+4]=[
            '-blockdev',json.dumps({'driver':'host_device','filename':raw,'node-name':'ssd-file','read-only':True}),
            '-blockdev',json.dumps({'driver':'raw','file':'ssd-file','node-name':'ssd-source','read-only':True}),
            '-blockdev',json.dumps({'driver':'file','filename':str(overlay),'node-name':'overlay-file'}),
            '-blockdev',json.dumps({'driver':'qcow2','file':'overlay-file','backing':'ssd-source','node-name':'disk'}),
            '-device','virtio-blk-pci,drive=disk']
    if a.action=='reset':print('Reset creates fresh 64GiB Android userdata in unused SSD space; existing boot/system/log partitions and old userdata bytes are retained.',flush=True)
    print('Running',a.action,'against',a.disk,'only. Reports:',work,flush=True)
    # No fixed timeout interrupts a GPT commit or filesystem resize. Ctrl-C can
    # leave an unfinished copy; the old GPT remains until all copy checks pass.
    with (work/'vm-console.txt').open('wb') as log:
        result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
    status=subprocess.run([a.mcopy,'-i',str(fat),'::/status.txt','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    output=work/'reports';output.mkdir()
    subprocess.run([a.mcopy,'-s','-i',str(fat),'::*',str(output)],check=True)
    archive=work.with_name(work.name+'-reports.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for file in [work/'disk-identity.plist',work/'vm-console.txt',*output.rglob('*')]:
            if file.is_file():z.write(file,str(file.relative_to(work)))
    # Root-owned reports remain readable to the invoking user; no full device
    # image or copied app data is added to the report ZIP.
    if os.environ.get('SUDO_UID') and os.environ.get('SUDO_GID'):
        uid,gid=int(os.environ['SUDO_UID']),int(os.environ['SUDO_GID'])
        for file in [work,*work.rglob('*'),archive]:os.chown(file,uid,gid)
    print('Report archive:',archive,flush=True)
    if result.returncode or status.returncode or status.stdout.strip()!=b'0':
        sys.exit('Maintenance did not complete successfully. Preserve reports and work.fat; do not assume a resize occurred.')
    print('Completed',a.action,flush=True)
    if a.action in ('expand','reset'):print('Eject and reconnect the SSD before using its refreshed partition layout.')
    else:print('Report collection completed; check the report for filesystem errors. The SSD was exposed read-only.')

if __name__=='__main__':main()
