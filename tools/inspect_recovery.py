#!/usr/bin/env python3
"""Read-only GPT, Android boot v3/v4 and liblp inspector; no mounts/root needed."""
import argparse, gzip, hashlib, json, pathlib, struct, subprocess, zlib

def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def align(n,p): return (n+p-1)//p*p
def digest(b): return hashlib.sha256(b).hexdigest()
def writejson(p,d): p.write_text(json.dumps(d,indent=2)+'\n')

def gpt(f):
    f.seek(512); h=f.read(512); assert h[:8]==b'EFI PART'
    hc=bytearray(h[:u32(h,12)]); hc[16:20]=bytes(4)
    assert zlib.crc32(hc)==u32(h,16)
    lba,count,size=struct.unpack_from('<QII',h,72)
    f.seek(lba*512); es=f.read(count*size); assert zlib.crc32(es)==u32(h,88)
    backup_lba=struct.unpack_from('<Q',h,32)[0]
    f.seek(backup_lba*512); bh=f.read(512);assert bh[:8]==b'EFI PART'
    bc=bytearray(bh[:u32(bh,12)]);bc[16:20]=bytes(4);assert zlib.crc32(bc)==u32(bh,16)
    bl,nb,sb=struct.unpack_from('<QII',bh,72);assert (nb,sb)==(count,size)
    f.seek(bl*512);be=f.read(nb*sb);assert zlib.crc32(be)==u32(bh,88) and be==es
    parts=[]
    for i in range(count):
        e=es[i*size:(i+1)*size]
        if not any(e[:16]): continue
        s,t,attrs=struct.unpack_from('<QQQ',e,32)
        import uuid
        parts.append(dict(index=i+1,name=e[56:128].decode('utf-16le').rstrip('\0'),
            offset=s*512,bytes=(t-s+1)*512,first_lba=s,last_lba=t,attributes=attrs,
            type_guid=str(uuid.UUID(bytes_le=e[:16])),guid=str(uuid.UUID(bytes_le=e[16:32]))))
    return parts

def liblp(f,base):
    f.seek(base+4096);g=f.read(4096);assert u32(g,0)==0x616c4467
    gg=bytearray(g[:u32(g,4)]);gg[8:40]=bytes(32);assert digest(gg)==g[8:40].hex()
    sz,count,bs=struct.unpack_from('<III',g,40); slots=[]
    for slot in range(count*2):
        f.seek(base+12288+slot*sz); m=f.read(sz)
        if u32(m,0)!=0x414c5030: slots.append({'slot':slot,'empty':True});continue
        hs=u32(m,8); h=bytearray(m[:hs]);h[12:44]=bytes(32)
        assert digest(h)==m[12:44].hex();assert digest(m[hs:hs+u32(m,44)])==m[48:80].hex()
        po,pc,ps=struct.unpack_from('<III',m,80);eo,ec,es=struct.unpack_from('<III',m,92)
        go,gc,gs=struct.unpack_from('<III',m,104);bo,bc,bss=struct.unpack_from('<III',m,116)
        groups=[];devices=[];parts=[]
        for i in range(gc):
            x=m[hs+go+i*gs:hs+go+(i+1)*gs]
            groups.append(dict(name=x[:36].split(b'\0')[0].decode(),flags=u32(x,36),max_bytes=struct.unpack_from('<Q',x,40)[0]))
        for i in range(bc):
            x=m[hs+bo+i*bss:hs+bo+(i+1)*bss]
            devices.append(dict(first_logical_sector=struct.unpack_from('<Q',x,0)[0],alignment=u32(x,8),
              alignment_offset=u32(x,12),bytes=struct.unpack_from('<Q',x,16)[0],name=x[24:60].split(b'\0')[0].decode(),flags=u32(x,60)))
        for i in range(pc):
            x=m[hs+po+i*ps:hs+po+(i+1)*ps]; first,num,group=struct.unpack_from('<III',x,40);ext=[]
            for j in range(first,first+num):
                n,k,t,s=struct.unpack_from('<QIQI',m,hs+eo+j*es)
                ext.append(dict(bytes=n*512,target_type=k,target_sector=t,source=s,absolute_offset=base+t*512 if k==0 else None))
            parts.append(dict(name=x[:36].split(b'\0')[0].decode(),attributes=u32(x,36),group=group,bytes=sum(e['bytes'] for e in ext),extents=ext))
        slots.append(dict(slot=slot,version=list(struct.unpack_from('<HH',m,4)),header_bytes=hs,flags=u32(m,128) if hs>=132 else None,partitions=parts,groups=groups,block_devices=devices))
    return dict(metadata_max_size=sz,metadata_slot_count=count,logical_block_size=bs,slots=slots)

def decompress(b):
    if b.startswith(b'\x1f\x8b'):return gzip.decompress(b)
    if b[:4] in (bytes.fromhex('02214c18'),bytes.fromhex('04224d18')):return subprocess.check_output(['lz4','-d','-c'],input=b)
    if b.startswith(b'070701'):return b
    raise ValueError('Unknown ramdisk compression '+b[:16].hex())

def extract_cpio(b,out):
    """Extract only regular files; inventory records symlinks/ownership without privileged writes."""
    out.mkdir(exist_ok=True); pos=0; rows=[]
    while pos+110<=len(b):
        if b[pos:pos+6] not in (b'070701',b'070702'):break
        vals=[int(b[pos+6+i*8:pos+14+i*8],16) for i in range(13)]
        mode,uid,gid,mtime,size,nlen=vals[1],vals[2],vals[3],vals[5],vals[6],vals[11]
        name=b[pos+110:pos+110+nlen-1].decode(); start=align(pos+110+nlen,4);data=b[start:start+size];pos=align(start+size,4)
        if name=='TRAILER!!!':continue
        p=pathlib.PurePosixPath(name);assert not p.is_absolute() and '..' not in p.parts
        row=dict(name=name,mode=oct(mode),uid=uid,gid=gid,mtime=mtime,bytes=size)
        if mode&0o170000==0o100000:
            dest=out/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);row['sha256']=digest(data)
        elif mode&0o170000==0o120000:row['symlink']=data.decode(errors='replace')
        rows.append(row)
    writejson(out/'cpio-inventory.json',rows)

def boot(b,name,out):
    d=out/name;d.mkdir(exist_ok=True);info={'bytes':len(b),'sha256':digest(b)}
    def save(n,x): (d/n).write_bytes(x); return {'file':n,'bytes':len(x),'sha256':digest(x)}
    if b[:8]==b'ANDROID!':
        v=u32(b,40);assert v in (3,4)
        ks,rs=struct.unpack_from('<II',b,8);hs=u32(b,20)
        info.update(header_version=v,header_bytes=hs,kernel_bytes=ks,ramdisk_bytes=rs,os_version_raw=u32(b,16),cmdline=b[44:1580].split(b'\0')[0].decode(),signature_bytes=u32(b,1580) if v==4 else 0)
        if ks:info['kernel']=save('kernel',b[4096:4096+ks])
        r=b[4096+align(ks,4096):4096+align(ks,4096)+rs]
        if rs:save('ramdisk',r);raw=decompress(r);save('ramdisk.cpio',raw);extract_cpio(raw,d/'ramdisk-files')
    elif b[:8]==b'VNDRBOOT':
        v,page=struct.unpack_from('<II',b,8);vs,hs,dtbs=u32(b,24),u32(b,2096),u32(b,2100)
        info.update(header_version=v,page_size=page,header_bytes=hs,ramdisk_bytes=vs,dtb_bytes=dtbs,cmdline=b[28:2076].split(b'\0')[0].decode(),board_name=b[2080:2096].split(b'\0')[0].decode())
        start=align(hs,page);dtbstart=start+align(vs,page)
        if dtbs:save('dtb',b[dtbstart:dtbstart+dtbs])
        ts,count,es,bs=struct.unpack_from('<IIII',b,2112);table=dtbstart+align(dtbs,page)
        info.update(table_bytes=ts,fragment_count=count,entry_bytes=es,bootconfig_bytes=bs,fragments=[])
        for i in range(count):
            e=b[table+i*es:table+(i+1)*es];size,off,kind=struct.unpack_from('<III',e)
            n=e[12:44].split(b'\0')[0].decode() or 'platform'; assert n.replace('_','').replace('-','').isalnum()
            r=b[start+off:start+off+size];bn=f'fragment-{i}-{n}'
            info['fragments'].append(dict(index=i,name=n,type=kind,offset=off,bytes=size,board_id=list(struct.unpack_from('<16I',e,44))))
            save(bn,r);raw=decompress(r);save(bn+'.cpio',raw);extract_cpio(raw,d/(bn+'-files'))
        save('bootconfig',b[table+align(ts,page):table+align(ts,page)+bs])
    else:info['magic']=b[:16].hex()
    writejson(d/'header.json',info);return info

def copy_range(f,start,n,dst):
    h=hashlib.sha256()
    with dst.open('wb') as o:
        f.seek(start)
        while n:
            b=f.read(min(n,8<<20));assert b;h.update(b)
            if not b.strip(b'\0'):o.seek(len(b),1)
            else:o.write(b)
            n-=len(b)
        o.truncate()
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('image',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);p.add_argument('--extract-logical',nargs='*',default=[]);p.add_argument('--include-b',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    with a.image.open('rb') as f:
        parts=gpt(f);writejson(a.out/'gpt.json',parts)
        for x in parts:
            n=x['name']
            if n.startswith(('boot_','init_boot_','vendor_boot_','vbmeta')) or n in ('misc','bootloader_a','pvmfw_a'):
                # A slot only for large boot images; both vbmeta copies retained.
                if n.endswith('_b') and not n.startswith('vbmeta') and not a.include_b:continue
                dst=a.out/(n+'.img');sha=copy_range(f,x['offset'],x['bytes'],dst)
                if n.startswith(('boot_','init_boot_','vendor_boot_')):boot(dst.read_bytes(),n,a.out)
        s=next(x for x in parts if x['name']=='super');lp=liblp(f,s['offset']);writejson(a.out/'super.json',lp)
        for x in lp['slots'][0]['partitions']:
            if x['name'] not in a.extract_logical:continue
            d=a.out/(x['name']+'.img');h=hashlib.sha256()
            with d.open('wb') as o:
                for e in x['extents']:
                    assert e['target_type']==0 and e['source']==0
                    f.seek(e['absolute_offset']);n=e['bytes']
                    while n:
                        b=f.read(min(n,8<<20));assert b;o.write(b);h.update(b);n-=len(b)
            writejson(a.out/(x['name']+'-hash.json'),dict(bytes=x['bytes'],sha256=h.hexdigest()))
    print(json.dumps(parts,indent=2))

if __name__=='__main__':main()
