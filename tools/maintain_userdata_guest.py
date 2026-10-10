#!/usr/bin/env python3
"""Offline userdata inspection/relocation, only inside the isolated tool VM.

Original filesystem and all other partition extents are never written. Apply
copies userdata into unused tail space, checks/resizes the copy, then commits
GPT. Original GPT backups stay on the separate local work disk.
"""
import contextlib,fcntl,hashlib,json,os,pathlib,stat,struct,subprocess,uuid,zlib
from inspect_recovery import gpt
DISK=pathlib.Path('/dev/vdb');WORK=pathlib.Path('/work')
USER_GUID='45c696f1-184d-4cc9-8cd9-ac0c710a35e6'
EXTRA={'GBRUNCH':'4ab7c001-7400-4bab-b412-43cbd52b9fb1','GBVENDOR':'4ab7c002-7400-4bab-b412-43cbd52b9fb1','GBLOG':'4ab7c003-7400-4bab-b412-43cbd52b9fb1'}

def layout(disk):
    with disk.open('rb') as f:
        parts=gpt(f);f.seek(0);mbr=f.read(512);header=f.read(512)
        tlba,count,esz=struct.unpack_from('<QII',header,72)
        assert tlba==2 and count==128 and esz==128
        f.seek(tlba*512);table=f.read(count*esz)
        backup_lba=struct.unpack_from('<Q',header,32)[0]
        f.seek(backup_lba*512);backup=f.read(512)
    assert mbr[510:512]==b'\x55\xaa' and mbr[450]==0xee
    by={p['name']:p for p in parts};assert len(by)==len(parts)
    u=by['userdata'];assert u['guid']==USER_GUID and u['index']==1
    assert u['bytes']>=4336885760
    for name,guid in EXTRA.items():assert by[name]['guid']==guid
    assert by['GBRUNCH']['bytes']==67108864 and by['GBLOG']['bytes']==268435456
    intervals=sorted((p['offset'],p['offset']+p['bytes']) for p in parts)
    assert all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:]))
    return parts,u,mbr,header,table,backup

def superblock(disk,offset):
    with disk.open('rb') as f:f.seek(offset+1024);b=f.read(1024)
    assert struct.unpack_from('<H',b,56)[0]==0xef53,'userdata is not ext4'
    size=1024<<struct.unpack_from('<I',b,24)[0]
    blocks=struct.unpack_from('<I',b,4)[0];free=struct.unpack_from('<I',b,12)[0]
    if struct.unpack_from('<I',b,96)[0]&0x80:
        blocks+=struct.unpack_from('<I',b,0x150)[0]<<32;free+=struct.unpack_from('<I',b,0x158)[0]<<32
    return {'block_size':size,'filesystem_bytes':blocks*size,'free_bytes':free*size,
            'inode_count':struct.unpack_from('<I',b,0)[0],'free_inodes':struct.unpack_from('<I',b,16)[0],
            'filesystem_uuid':str(uuid.UUID(bytes=b[104:120]))}

@contextlib.contextmanager
def loop(offset,size,readonly):
    control=os.open('/dev/loop-control',os.O_RDWR)
    try:number=fcntl.ioctl(control,0x4c82)
    finally:os.close(control)
    node=pathlib.Path('/dev/loop'+str(number))
    if not node.exists():os.mknod(node,stat.S_IFBLK|0o600,os.makedev(7,number))
    src=os.open(DISK,os.O_RDONLY if readonly else os.O_RDWR);fd=os.open(node,os.O_RDWR)
    attached=False
    try:
        fcntl.ioctl(fd,0x4c00,src);attached=True
        info=struct.pack('=QQQQQIIII64s64s32sQQ',0,0,0,offset,size,number,0,0,1 if readonly else 0,
                         str(DISK).encode().ljust(64,b'\0'),bytes(64),bytes(32),0,0)
        fcntl.ioctl(fd,0x4c04,info)
        yield node
    finally:
        if attached:fcntl.ioctl(fd,0x4c01)
        os.close(fd);os.close(src)

def command(name,*args,allowed=(0,)):
    with (WORK/(name+'.txt')).open('wb') as out:
        p=subprocess.run([str(a) for a in args],stdout=out,stderr=subprocess.STDOUT)
    assert p.returncode in allowed,(name,p.returncode)
    return p.returncode

def save(name,value):
    (WORK/name).write_text(json.dumps(value,indent=2)+'\n');os.sync()

def plan_target(parts,header,backup,capacity):
    target_size=64<<30
    old_start=struct.unpack_from('<Q',backup,72)[0]*512
    old_end=struct.unpack_from('<Q',header,32)[0]*512+512
    start=(max(p['offset']+p['bytes'] for p in parts)+1048575)//1048576*1048576
    if start<old_end and start+target_size>old_start:start=(old_end+1048575)//1048576*1048576
    last=capacity//512-1
    assert start+target_size<=(last-32)*512,'Not enough unused tail space'
    assert start+target_size<=old_start or start>=old_end
    return start,target_size,last

def main():
    assert 'gbrunch.userdata_vm=1' in pathlib.Path('/proc/cmdline').read_text()
    assert (WORK/'GBRUNCH-USERDATA-MARKER.txt').read_text()=='GBRUNCH isolated userdata maintenance\n'
    request=json.loads((WORK/'request.json').read_text());assert request['action'] in ['inspect','diagnose','expand','reset']
    assert request['gib']==64
    if request['action']=='diagnose':assert 'gbrunch.userdata_overlay=1' in pathlib.Path('/proc/cmdline').read_text()
    parts,u,mbr,header,table,backup=layout(DISK)
    capacity=int(pathlib.Path('/sys/class/block/vdb/size').read_text())*512
    before=superblock(DISK,u['offset']);assert before['filesystem_bytes']<=u['bytes']
    report={'action':request['action'],'disk_bytes':capacity,'userdata_partition':u,'before':before,
            'original_region_retained':True,'phase':'inspection'};save('report.json',report)
    with loop(u['offset'],u['bytes'],True) as node:
        command('filesystem-before','/bin/dumpe2fs','-h',node)
        report['readonly_fsck_exit']=command('fsck-before','/bin/e2fsck','-f','-n',node,allowed=(0,4,8,12))
        for kind in ['user','group','project']:
            command('quota-'+kind,'/bin/debugfs','-R','list_quota '+kind,node,allowed=(0,1))
        command('root-directory','/bin/debugfs','-R','ls -l /',node,allowed=(0,1))
        command('dalvik-cache','/bin/debugfs','-R','ls -l /dalvik-cache/x86_64',node,allowed=(0,1))
    if request['action']=='diagnose':
        # The host exposes a writable local overlay over an explicitly read-only
        # source device. Only replay committed journal transactions, no repairs.
        with loop(u['offset'],u['bytes'],False) as node:
            report['journal_replay_exit']=command('journal-replay','/bin/e2fsck','-p','-E','journal_only',node,allowed=(0,1,4,8,12))
            save('report.json',report)
            command('filesystem-after-replay','/bin/dumpe2fs','-h',node)
            report['after_replay']=superblock(DISK,u['offset'])
            report['replayed_fsck_exit']=command('fsck-after-replay','/bin/e2fsck','-f','-n',node,allowed=(0,4,8,12))
            for kind in ['user','group','project']:
                command('replayed-quota-'+kind,'/bin/debugfs','-R','list_quota '+kind,node,allowed=(0,1))
            for name, directory in [('root','/'),('dalvik-cache','/dalvik-cache/x86_64'),('settings','/user_de/0/com.android.providers.settings')]:
                command('replayed-directory-'+name,'/bin/debugfs','-R','ls -l '+directory,node,allowed=(0,1))
        report['phase']='overlay diagnosis complete';save('report.json',report);return
    if request['action']=='inspect':
        report['phase']='inspection complete';save('report.json',report);return
    assert u['offset']==14598275072 and u['bytes']==4336885760,'Already relocated or unsupported userdata geometry'
    start,target_size,last=plan_target(parts,header,backup,capacity)
    table_sectors=len(table)//512
    # Reject genuinely unrelated I/O faults; repairs are performed on the copy.
    if request['action']=='expand':assert report['readonly_fsck_exit'] in (0,4)
    report.update(phase='copying',new_offset=start,new_bytes=target_size);save('report.json',report)
    for name,b in [('original-mbr.bin',mbr),('original-primary-header.bin',header),('original-table.bin',table),('original-backup-header.bin',backup)]:
        (WORK/name).write_bytes(b)
    os.sync()
    if request['action']=='reset':
        report['phase']='formatting fresh userdata in unused tail space';save('report.json',report)
        features='none,has_journal,ext_attr,dir_index,filetype,extent,casefold,sparse_super,large_file,huge_file,uninit_bg,dir_nlink,extra_isize,quota,project,verity'
        with loop(start,target_size,False) as node:
            command('format-fresh','/bin/mke2fs','-F','-t','ext4','-b','4096','-I','512','-i','16384','-m','0',
                    '-O',features,'-E','encoding=utf8-12.1,lazy_itable_init=0,lazy_journal_init=0,nodiscard',
                    '-J','size=64','-U',before['filesystem_uuid'],'-M','/data',node)
            command('fsck-fresh','/bin/e2fsck','-f','-n',node)
            command('filesystem-after','/bin/dumpe2fs','-h',node)
            for kind in ['user','group','project']:
                command('fresh-quota-'+kind,'/bin/debugfs','-R','list_quota '+kind,node,allowed=(0,1))
        report['fresh_userdata']=True
    else:
        source_hash=hashlib.sha256()
        with DISK.open('r+b',buffering=0) as f:
            for pos in range(0,u['bytes'],4<<20):
                f.seek(u['offset']+pos);b=f.read(min(4<<20,u['bytes']-pos));assert b
                source_hash.update(b);f.seek(start+pos)
                view=memoryview(b)
                while view:
                    n=f.write(view);assert n;view=view[n:]
            os.fsync(f.fileno())
            target_hash=hashlib.sha256()
            f.seek(start);left=u['bytes']
            while left:
                b=f.read(min(left,4<<20));assert b;target_hash.update(b);left-=len(b)
            assert target_hash.digest()==source_hash.digest(),'Copy verification failed; GPT unchanged'
        report['copy_sha256']=source_hash.hexdigest();report['phase']='checking and resizing copy';save('report.json',report)
        with loop(start,target_size,False) as node:
            command('fsck-copy','/bin/e2fsck','-p','-f',node,allowed=(0,1))
            command('resize','/bin/resize2fs',node)
            command('fsck-expanded','/bin/e2fsck','-f','-n',node)
            command('filesystem-after','/bin/dumpe2fs','-h',node)
    after=superblock(DISK,start)
    assert after['filesystem_bytes']==target_size and after['filesystem_uuid']==before['filesystem_uuid']
    new_table=bytearray(table);struct.pack_into('<QQ',new_table,(u['index']-1)*128+32,start//512,(start+target_size)//512-1)
    for p in parts:
        if p['name']!='userdata':
            i=(p['index']-1)*128;assert table[i:i+128]==new_table[i:i+128]
    new_header=bytearray(header);struct.pack_into('<Q',new_header,32,last);struct.pack_into('<Q',new_header,48,last-table_sectors-1)
    struct.pack_into('<I',new_header,88,zlib.crc32(new_table));struct.pack_into('<I',new_header,16,0);struct.pack_into('<I',new_header,16,zlib.crc32(new_header[:92]))
    new_backup=bytearray(new_header);struct.pack_into('<QQ',new_backup,24,last,1);struct.pack_into('<Q',new_backup,72,last-table_sectors)
    struct.pack_into('<I',new_backup,16,0);struct.pack_into('<I',new_backup,16,zlib.crc32(new_backup[:92]))
    new_mbr=bytearray(mbr);struct.pack_into('<I',new_mbr,458,min(last,0xffffffff))
    report.update(phase='committing GPT',after=after);save('report.json',report)
    with DISK.open('r+b',buffering=0) as f:
        # Backup first: a valid new GPT remains recoverable during primary commit.
        for offset,b in [((last-table_sectors)*512,new_table),(last*512,new_backup)]:f.seek(offset);assert f.write(b)==len(b)
        os.fsync(f.fileno())
        for offset,b in [(1024,new_table),(512,new_header),(0,new_mbr)]:f.seek(offset);assert f.write(b)==len(b)
        os.fsync(f.fileno())
    newparts,newu,*_=layout(DISK);assert newu['offset']==start and newu['bytes']==target_size
    report['phase']='complete';save('report.json',report)

if __name__=='__main__':main()
