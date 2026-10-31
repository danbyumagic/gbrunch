#!/usr/bin/env python3
"""Derive a hardware-profile asset directory from an existing GBRUNCH asset kit.

The source kit is read-only. A NEW output directory receives a copy with:
  * pinned linux-firmware GPU files added to the initramfs firmware list,
  * pinned Wi-Fi/Bluetooth firmware written into a copy of compat.ext4 (/oem/firmware),
  * native-grub.cfg admission regenerated from googlebook_boot_menu.PROFILES,
  * native-assets.json file hashes updated and a profile record added.
Use the output with assemble_native_android.py --assets OUTPUT.
No Google recovery bytes are read or written, and no block devices are touched.
"""
import argparse,hashlib,json,os,pathlib,re,shutil,subprocess,sys,tempfile,urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from googlebook_boot_menu import smbios_gate

COMMIT='788aadc8f73d93908cf8545b2fc770fb6580a3f2'  # same linux-firmware commit as download_hp_radio_firmware.py
SOURCE='https://gitlab.com/kernel-firmware/linux-firmware/-/raw/'+COMMIT+'/'
FIRMWARE_LABEL='u:object_r:vendor_firmware_file:s0'
BASE_COMPAT='77cb6ec0e399a944a020b5d7d55d03dbd1bb5a2ba01012be91d315987ab69722'  # tested V7 compat.ext4
# Fixed e2fsprogs clock so the derived compat.ext4 is byte-reproducible and can be
# pinned in dualboot_installer.COMPAT_HASHES (2025-10-10T05:00:00Z, close to the V7 build).
FAKE_TIME='1760072400'
# target: 'initrd' -> /lib/firmware in the generated ramdisk (needed before /oem mounts),
#         'oem'    -> /oem/firmware (init.gbrunch.rc sets firmware_class.path there),
#         'license'-> licenses/ in the asset directory.
PROFILES={
 'hp-dragonfly-g4':{
  'board':'8B63',
  'compat_sha256':'a341d089c546ead50d8f25e196c46fb18b5781a68ebca6ccfaa2355e35f3e542',
  # Physical test 2026-10-31: with defaults the RPL-U eDP primary plane faulted
  # ("[PLANE:33:plane 1A] fault", Y-tiled XRGB via DPT) and the panel went black.
  # These xe display options removed every fault; setup and apps then worked.
  'cmdline_append':'xe.enable_psr=0 xe.enable_dpt=0 xe.enable_fbc=0',
  'evidence':'Ubuntu 7.0 live dmesg on the target: i915 adlp_dmc/adlp_guc_70/tgl_huc, iwlwifi so-a0-gf-a0-89 (8086:51f1 sub 8086:0094), btintel ibt-0040-0041 (8087:0033)',
  'files':[
   {'name':'i915/adlp_dmc.bin','target':'initrd','sha256':'3516de2e134ddcf3b319c75d2e437779fecbd58cbb77234bd6f297c544e92ccb','bytes':79088},
   {'name':'i915/adlp_guc_70.bin','target':'initrd','sha256':'451ee39d1dcd0c8169dfb6af7b585e4873e8bf5ca72e7625e4d79b9cc66c2f4c','bytes':341696},
   {'name':'i915/tgl_huc.bin','target':'initrd','sha256':'dbb1316bac13a76427ffa7827e52b5b9affe8a4cadd23dc22e2a54e35c53bdad','bytes':589888},
   {'name':'iwlwifi-so-a0-gf-a0-89.ucode','target':'oem','sha256':'73171b7b1e0ded4687772cf7faac1e87d7ebbb193704361542f1eac73086f401','bytes':1735944},
   {'name':'iwlwifi-so-a0-gf-a0.pnvm','target':'oem','sha256':'99b9fb2c88e4e9dbd0559a768190affc78846897764f7c9af21d29fd65ff69b7','bytes':55208},
   {'name':'intel/ibt-0040-0041.sfi','target':'oem','sha256':'e4d46a2d9c0fe973c1a62a037c9a792df9b8aa2f5bf072eedd63b2c03ef3fdf9','bytes':719012},
   {'name':'intel/ibt-0040-0041.ddc','target':'oem','sha256':'fe272982577efdc289cfe3e8bedafca607c0b7d6c9df1aab1880e22ef930d077','bytes':9},
   {'name':'LICENSE.i915','target':'license','sha256':'8542aeabf2761935122d693561e16766ce1bcc2b0d003204f9040b7d6d929f2e','bytes':2080},
   {'name':'LICENCE.iwlwifi_firmware','target':'license','sha256':'16d5040c7cf851fc693b7542e20870935b99802533ea1bfd231c377a2305e5c5','bytes':2046},
   {'name':'LICENCE.ibt_firmware','target':'license','sha256':'5181b0b51efc79d5acb2c9bb92042878fdbad97a92114d4ab5e32e2b5b52fce4','bytes':2040},
  ]},
}

ENV=dict(os.environ,E2FSPROGS_FAKE_TIME=FAKE_TIME)

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def fetch(entry,cache):
    path=cache/entry['name']
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True);part=path.with_name(path.name+'.download')
        print('Downloading',SOURCE+entry['name'],flush=True)
        with urllib.request.urlopen(SOURCE+entry['name'],timeout=60) as r:part.write_bytes(r.read())
        part.rename(path)
    if path.stat().st_size!=entry['bytes'] or sha(path)!=entry['sha256']:
        raise ValueError('Pinned firmware mismatch: '+str(path))
    return path

def debugfs(image,*commands):
    with tempfile.NamedTemporaryFile('w',suffix='.cmd',delete=False) as f:
        f.write('\n'.join(commands)+'\n');script=f.name
    try:
        out=subprocess.run(['debugfs','-w','-f',script,str(image)],check=True,capture_output=True,text=True,env=ENV)
    finally:pathlib.Path(script).unlink()
    bad=[l for l in out.stderr.splitlines() if l.strip() and not l.startswith('debugfs ')]
    if bad:raise RuntimeError('debugfs: '+'\n'.join(bad))

def exists_in(image,path):
    out=subprocess.run(['debugfs','-R','stat '+path,str(image)],capture_output=True,text=True,env=ENV)
    return 'Inode:' in out.stdout

def add_oem_firmware(image,entries):
    for e,src in entries:
        dest='/firmware/'+e['name']
        parent=dest.rsplit('/',1)[0]
        if not exists_in(image,parent):
            debugfs(image,'mkdir '+parent,'sif %s mode 040755'%parent,'sif %s uid 0'%parent,'sif %s gid 0'%parent,
                    'ea_set %s security.selinux %s'%(parent,FIRMWARE_LABEL))
        if exists_in(image,dest):raise ValueError('Refusing to replace existing '+dest)
        debugfs(image,'write %s %s'%(src,dest),'sif %s mode 0100644'%dest,'sif %s uid 0'%dest,'sif %s gid 0'%dest,
                'ea_set %s security.selinux %s'%(dest,FIRMWARE_LABEL))
    subprocess.run(['e2fsck','-fn',str(image)],check=True,capture_output=True,env=ENV)

def regenerate_gate(cfg):
    # Replace the SMBIOS admission block of the default entry with the shared profile list.
    m=re.search(r"(menuentry '[^']*' \{\n)( insmod smbios\n.*?)( if \[ \"\$allowed\" = \"1\" \]; then\n)",cfg,re.S)
    if not m:raise ValueError('native-grub.cfg: admission block not found')
    cfg=cfg[:m.start(2)]+smbios_gate()+cfg[m.end(2):]
    return cfg.replace("This experiment is restricted to the tested HP 15-fe1xxx / 8C4F or QEMU.",
                       "This experiment requires a known hardware profile (exact SMBIOS match) or QEMU.")

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--assets',required=True,type=pathlib.Path,help='existing kit assets directory (read only)')
    p.add_argument('--output',required=True,type=pathlib.Path,help='NEW output assets directory')
    p.add_argument('--profile',default='hp-dragonfly-g4',choices=sorted(PROFILES))
    p.add_argument('--firmware-cache',type=pathlib.Path,default=pathlib.Path('profile-firmware-cache'))
    a=p.parse_args();src=a.assets.resolve();out=a.output.absolute();profile=PROFILES[a.profile]
    if out.exists() or out.is_symlink():p.error('Output must not exist')
    if not shutil.which('debugfs') or not shutil.which('e2fsck'):p.error('Missing e2fsprogs (debugfs, e2fsck)')
    manifest=json.loads((src/'native-assets.json').read_text())
    for n,h in manifest['files'].items():
        if sha(src/n)!=h:raise ValueError('Source asset hash mismatch: '+n)
    cache=a.firmware_cache.resolve()/COMMIT;fetched=[(e,fetch(e,cache)) for e in profile['files']]
    tmp=out.with_name(out.name+'.partial')
    if tmp.exists():p.error('Remove stale '+str(tmp))
    shutil.copytree(src,tmp,symlinks=False)
    try:
        known={v['name'] for v in manifest['firmware']}
        for e,f in fetched:
            if e['target']=='initrd':
                if e['name'] in known:continue
                dest=tmp/'firmware'/e['name'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)
                manifest['firmware'].append({'name':e['name'],'sha256':e['sha256'],'bytes':e['bytes'],'package':'linux-firmware '+COMMIT})
            elif e['target']=='license':
                shutil.copyfile(f,tmp/'licenses'/e['name'])
        add_oem_firmware(tmp/'compat.ext4',[(e,f) for e,f in fetched if e['target']=='oem'])
        compat=sha(tmp/'compat.ext4')
        if manifest['files']['compat.ext4']==BASE_COMPAT and compat!=profile['compat_sha256']:
            raise ValueError('Derived compat.ext4 %s differs from the pinned profile image %s'%(compat,profile['compat_sha256']))
        if manifest['files']['compat.ext4']!=BASE_COMPAT:
            print('WARNING: source kit is not the tested V7 image; the trial/installer will refuse this compat.ext4',flush=True)
        cfg=tmp/'native-grub.cfg';cfg.write_text(regenerate_gate(cfg.read_text()))
        extra=profile.get('cmdline_append','')
        if extra and extra not in manifest['cmdline']:
            if not re.fullmatch(r'[A-Za-z0-9_.=, -]+',extra):raise ValueError('Unsafe cmdline_append')
            manifest['cmdline']=manifest['cmdline'].replace(' androidboot.init_rc=',' '+extra+' androidboot.init_rc=',1)
            assert extra in manifest['cmdline'],'cmdline anchor androidboot.init_rc= not found'
        record={'profile':a.profile,'board':profile['board'],'cmdline_append':profile.get('cmdline_append',''),'status':'profile: inventory-matched, Android boot not yet observed',
                'evidence':profile['evidence'],'source':SOURCE,'source_kit_compat_sha256':manifest['files']['compat.ext4'],
                'files':[{k:e[k] for k in ['name','target','sha256','bytes']} for e,_ in fetched]}
        (tmp/('profile-'+a.profile+'.json')).write_text(json.dumps(record,indent=2)+'\n')
        files={}
        for f in sorted(tmp.rglob('*')):
            if f.is_file() and f.name!='native-assets.json':files[str(f.relative_to(tmp))]=sha(f)
        manifest['files']=files;manifest['scope']+=' + '+a.profile+' firmware profile'
        (tmp/'native-assets.json').write_text(json.dumps(manifest,indent=2)+'\n')
        tmp.rename(out)
    except BaseException:
        shutil.rmtree(tmp,ignore_errors=True);raise
    print(json.dumps({'output':str(out),'profile':a.profile,'initrd_firmware':len(manifest['firmware']),
                      'oem_firmware_added':sum(e['target']=='oem' for e,_ in fetched),'compat_sha256':files['compat.ext4']},indent=2))

if __name__=='__main__':main()
