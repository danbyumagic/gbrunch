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
import argparse,base64,gzip,hashlib,io,json,os,pathlib,tarfile,re,shutil,subprocess,sys,tempfile,urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from googlebook_boot_menu import smbios_gate

COMMIT='788aadc8f73d93908cf8545b2fc770fb6580a3f2'  # same linux-firmware commit as download_hp_radio_firmware.py
SOURCE='https://gitlab.com/kernel-firmware/linux-firmware/-/raw/'+COMMIT+'/'
FIRMWARE_LABEL='u:object_r:vendor_firmware_file:s0'
BASE_COMPAT='77cb6ec0e399a944a020b5d7d55d03dbd1bb5a2ba01012be91d315987ab69722'  # tested V7 compat.ext4
# Fixed e2fsprogs clock so the derived compat.ext4 is byte-reproducible and can be
# pinned in dualboot_installer.COMPAT_HASHES (2025-10-10T05:00:00Z, close to the V7 build).
FAKE_TIME='1760072400'
# Debian packages used as pinned firmware sources (entries with 'deb' and 'member').
DEBS={
 'firmware-sof-signed':{'url':'https://deb.debian.org/debian/pool/non-free-firmware/f/firmware-sof/firmware-sof-signed_2026.09.2-1_all.deb',
                        'sha256':'eb9ff4928b739ae88e63261839299951a66b27a01e573622e0213ac14f0aa609'},
}
# Extra logger capture: backlight sysfs and ALSA state, for brightness/audio bring-up.
LOGGER_ANCHOR='''    capture "$n-wifi.txt" dumpsys -t 5 wifi
'''
LOGGER_CAPTURE='''    capture "$n-backlight-audio.txt" sh -c 'for d in /sys/class/backlight/*; do echo "== $d"; for f in type max_brightness brightness actual_brightness bl_power; do echo "$f=$(cat $d/$f)"; done; done; cat /proc/asound/cards /proc/asound/pcm; ls -l /dev/snd; dumpsys -t 5 media.audio_flinger | head -200; dumpsys -t 5 media.audio_policy | head -200'
    capture "$n-audio-logcat.txt" sh -c 'logcat -b all -d -v threadtime | grep -iE "audio|dras|APM_|soundcard|hal_?config|sofhdadsp|sof-hda|tinyalsa|mixer|alsa" | tail -c 1048576'
    capture "$n-battery.txt" sh -c 'dumpsys -t 5 battery; for d in /sys/class/power_supply/*; do echo "== $d -> $(readlink -f $d)"; for f in type online status capacity; do echo "$f=$(cat $d/$f)"; done; done'
'''
PROFILE_DIR=pathlib.Path(__file__).resolve().parents[1]/'profiles'
INIT_ANCHOR='''    mount none /oem/weaver-manifest.xml /vendor/etc/vintf/manifest/android.hardware.weaver-service.android-desktop.xml bind
'''
# target: 'initrd' -> /lib/firmware in the generated ramdisk (needed before /oem mounts),
#         'oem'    -> /oem/firmware (init.gbrunch.rc sets firmware_class.path there),
#         'license'-> licenses/ in the asset directory.
PROFILES={
 'hp-dragonfly-g4':{
  'board':'8B63',
  'compat_sha256':'26d046edc88535794ca8395355462a06758b22300a5cda88b14d37c1073aec43',
  # Physical test 2026-10-31: with defaults the RPL-U eDP primary plane faulted
  # ("[PLANE:33:plane 1A] fault", Y-tiled XRGB via DPT) and the panel went black.
  # These xe display options removed every fault; setup and apps then worked.
  # snd_intel_dspcfg.dsp_driver=3: force SOF. Otherwise snd_soc_avs claims 8086:51ca, finds no
  # intel/avs/adl/dsp_basefw.bin and leaves "No soundcards found" (physical test 2026-10-31).
  # Ruby's vendor_dlkm modules.options sets "snd_sof_intel_hda_generic hda_model=alc-2024y-chromebook
  # dmic_num=4". libmodprobe appends kernel-cmdline module options, so these override it: 2 DMICs (NHLT),
  # and an unknown model name so the ALC245 falls back to its 103c:8b63 SSID quirk.
  'cmdline_append':'xe.enable_psr=0 xe.enable_dpt=0 xe.enable_fbc=0 snd_intel_dspcfg.dsp_driver=3 '
                   'snd_sof_intel_hda_generic.dmic_num=2 snd_sof_intel_hda_generic.hda_model=auto',
  'logger_capture':True,
  # Owned files under profiles/<name>/oem, written to /oem with the given SELinux label, and
  # file bind mounts added to init.gbrunch.rc early-init (init may mount on vendor_configs_file files).
  'oem_files':[('audio/hal_audio.xml','vendor_configs_file'),('audio/audio_config.xml','vendor_configs_file'),
               ('audio/mixer_paths.xml','vendor_configs_file')],
  # Files added to the locally derived GBVENDOR (vendor.erofs) by the tool VM. DRAS cannot resolve a
  # SKU/model on non-Google hardware (no ro.boot.product.hardware.id), so it reads its fallback paths
  # /vendor/etc/{audio_config,mixer_paths,volume_curves}.xml, which do not exist in Ruby's vendor.
  # 'src' is an owned profile file; 'copy_from' copies a file of the local recovery inside the VM,
  # so no Google bytes enter the public kit. 'template' supplies mode/owner/SELinux xattrs.
  'vendor_files':[
   {'path':'etc/audio_config.xml','src':'vendor/etc/audio_config.xml','template':'/etc/audio_policy_configuration.xml'},
   {'path':'etc/mixer_paths.xml','src':'vendor/etc/mixer_paths.xml','template':'/etc/audio_policy_configuration.xml'},
   {'path':'etc/volume_curves.xml','copy_from':'/etc/audio/sof-rt5682_alc5682ivs_tas2563/volume_curves.xml','template':'/etc/audio_policy_configuration.xml'},
  ],
  # Out-of-tree GKI modules from tools/build_gki_modules.py (--gki-modules DIR), loaded by init.
  # ac.ko: ACPI0003 AC adapter. Ruby's vendor modules ship battery.ko but not ac.ko, so Android
  # never saw the charger (AC powered: false).
  'oem_modules':[{'file':'ac.ko','sha256':'773b704764e4b45ad853630c986634a54146ddcd65fbe5a0009ea6c421ffe680'}],
  'init_binds':[('/oem/audio/hal_audio.xml','/vendor/etc/data/hal_configs/audio_default.xml'),
                ('/oem/audio/hal_audio.xml','/vendor/etc/data/hal_configs/audio_alc5682i_tas2563rppr.xml'),
                ('/oem/audio/audio_config.xml','/vendor/etc/audio/sof-rt5682_alc5682ivs_tas2563/audio_config.xml'),
                ('/oem/audio/mixer_paths.xml','/vendor/etc/audio/sof-rt5682_alc5682ivs_tas2563/mixer_paths.xml')],
  'evidence':'Ubuntu 7.0 live dmesg on the target: i915 adlp_dmc/adlp_guc_70/tgl_huc, iwlwifi so-a0-gf-a0-89 (8086:51f1 sub 8086:0094), btintel ibt-0040-0041 (8087:0033)',
  'files':[
   {'name':'i915/adlp_dmc.bin','target':'initrd','sha256':'3516de2e134ddcf3b319c75d2e437779fecbd58cbb77234bd6f297c544e92ccb','bytes':79088},
   {'name':'i915/adlp_guc_70.bin','target':'initrd','sha256':'451ee39d1dcd0c8169dfb6af7b585e4873e8bf5ca72e7625e4d79b9cc66c2f4c','bytes':341696},
   {'name':'i915/tgl_huc.bin','target':'initrd','sha256':'dbb1316bac13a76427ffa7827e52b5b9affe8a4cadd23dc22e2a54e35c53bdad','bytes':589888},
   {'name':'iwlwifi-so-a0-gf-a0-89.ucode','target':'oem','sha256':'73171b7b1e0ded4687772cf7faac1e87d7ebbb193704361542f1eac73086f401','bytes':1735944},
   {'name':'iwlwifi-so-a0-gf-a0.pnvm','target':'oem','sha256':'99b9fb2c88e4e9dbd0559a768190affc78846897764f7c9af21d29fd65ff69b7','bytes':55208},
   {'name':'intel/ibt-0040-0041.sfi','target':'oem','sha256':'e4d46a2d9c0fe973c1a62a037c9a792df9b8aa2f5bf072eedd63b2c03ef3fdf9','bytes':719012},
   {'name':'intel/ibt-0040-0041.ddc','target':'oem','sha256':'fe272982577efdc289cfe3e8bedafca607c0b7d6c9df1aab1880e22ef930d077','bytes':9},
   # SOF for RPL-P (8086:51ca), HDA codec ALC245 + 2 DMICs. Both IPC3 and IPC4 sets, since the
   # GKI default IPC for RPL is not established; Ubuntu 7.0 used IPC3 with the -2ch topology.
   {'name':'intel/sof/sof-rpl.ri','target':'oem','deb':'firmware-sof-signed','member':'usr/lib/firmware/intel/sof/intel-signed/sof-adl.ri','sha256':'294e5a51b1d3fc4ceda57780927c2a2ec95bb5d23477f879a9fb648c6c01cb30','bytes':525056},
   {'name':'intel/sof-tplg/sof-hda-generic-2ch.tplg','target':'oem','deb':'firmware-sof-signed','member':'usr/lib/firmware/intel/sof-tplg/sof-hda-generic-2ch.tplg','sha256':'7896ab52853e64d063f5e897011d200c2944732d75a96787667454fe2f443c53','bytes':44247},
   # 4ch topologies too, in case the dmic_num override is not applied (Ruby default requests -4ch).
   {'name':'intel/sof-tplg/sof-hda-generic-4ch.tplg','target':'oem','deb':'firmware-sof-signed','member':'usr/lib/firmware/intel/sof-tplg/sof-hda-generic-4ch.tplg','sha256':'7b1b185b35f1034ca1957f41e75c184f79ea1cae7b38bcef995acf7481145d20','bytes':44383},
   {'name':'intel/sof-ipc4-tplg/sof-hda-generic-4ch.tplg','target':'oem','deb':'firmware-sof-signed','member':'usr/lib/firmware/intel/sof-ipc4-tplg/sof-hda-generic-4ch.tplg','sha256':'381712d6b22d0bcdabc1d84ac5be083efe874b71691484211b1d22bc56a54ebe','bytes':60366},
   {'name':'intel/sof-ipc4/rpl/sof-rpl.ri','target':'oem','deb':'firmware-sof-signed','member':'usr/lib/firmware/intel/sof-ipc4/rpl/intel-signed/sof-rpl.ri','sha256':'351325786e53ca7cd23ffc1462d82913f3e0c08ad78f89053d85e4b6703cf12b','bytes':707036},
   {'name':'intel/sof-ipc4-tplg/sof-hda-generic-2ch.tplg','target':'oem','deb':'firmware-sof-signed','member':'usr/lib/firmware/intel/sof-ipc4-tplg/sof-hda-generic-2ch.tplg','sha256':'6d1313cf7311dcc47ccb78a05841f25da9640c4e87cb04a346ddf56f43f13f7b','bytes':60982},
   {'name':'firmware-sof-signed.copyright','target':'license','deb':'firmware-sof-signed','member':'usr/share/doc/firmware-sof-signed/copyright','sha256':'f769db7d9007c9e2c6aaa4076fc6604e771c88c685c2fda4045e0d0ab11ffc06','bytes':109946},
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

def deb_member(entry,cache):
    pkg=DEBS[entry['deb']];deb=cache/'debs'/pkg['url'].rsplit('/',1)[1]
    if not deb.exists():
        deb.parent.mkdir(parents=True,exist_ok=True);part=deb.with_name(deb.name+'.download')
        print('Downloading',pkg['url'],flush=True)
        with urllib.request.urlopen(pkg['url'],timeout=120) as r:part.write_bytes(r.read())
        part.rename(deb)
    if sha(deb)!=pkg['sha256']:raise ValueError('Pinned package mismatch: '+str(deb))
    tar=subprocess.run(['dpkg-deb','--fsys-tarfile',str(deb)],check=True,capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        m=t.getmember('./'+entry['member'])
        if not m.isfile():raise ValueError('Package member is not a regular file: '+entry['member'])
        return t.extractfile(m).read()

def fetch(entry,cache):
    if 'deb' in entry:
        path=cache/'from-deb'/entry['deb']/entry['name']
        if not path.exists():
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(deb_member(entry,cache))
    else:
        path=cache/COMMIT/entry['name']
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
        parts=dest.split('/')[1:-1]
        for i in range(2,len(parts)+1):  # /firmware itself exists; create missing descendants top-down
            parent='/'+'/'.join(parts[:i])
            if not exists_in(image,parent):
                debugfs(image,'mkdir '+parent,'sif %s mode 040755'%parent,'sif %s uid 0'%parent,'sif %s gid 0'%parent,
                        'ea_set %s security.selinux %s'%(parent,FIRMWARE_LABEL))
        if exists_in(image,dest):raise ValueError('Refusing to replace existing '+dest)
        debugfs(image,'write %s %s'%(src,dest),'sif %s mode 0100644'%dest,'sif %s uid 0'%dest,'sif %s gid 0'%dest,
                'ea_set %s security.selinux %s'%(dest,FIRMWARE_LABEL))
    subprocess.run(['e2fsck','-fn',str(image)],check=True,capture_output=True,env=ENV)

# Patch for the tool VM's payload/native_vendor_in_vm.py (V7 initrd version): add profile files from
# /payload/extra-vendor.json to the vendor overlay, taking metadata from an existing template path.
VM_PATCHES=[
 ("""    for n in TOOLS:
""","""    extra=json.loads(pathlib.Path('/payload/extra-vendor.json').read_text()) if pathlib.Path('/payload/extra-vendor.json').exists() else []
    template={}
    for e in extra:
        data=extract(e['copy_from']) if 'copy_from' in e else __import__('base64').b64decode(e['data'])
        assert 'copy_from' in e or hashlib.sha256(data).hexdigest()==e['sha256'],e['path']
        overlays[e['path']]=data;template[e['path']]=e['template']
    for n in TOOLS:
"""),
 ("""            m=meta(SOURCE,'/'+n,OFFSET);ti=tarfile.TarInfo(n);ti.size=len(b)""",
  """            m=meta(SOURCE,template.get(n,'/'+n),OFFSET);ti=tarfile.TarInfo(n);ti.size=len(b)"""),
]

def cpio_newc(entries):
    out=b''
    for i,(name,mode,data) in enumerate(entries+[('TRAILER!!!',0,b'')]):
        n=name.encode()+b'\0';fields=[880000+i,mode,0,0,1,0,len(data),0,0,0,0,len(n),0]
        h=b'070701'+b''.join(b'%08x'%v for v in fields)+n
        out+=h+bytes(-len(h)%4)+data+bytes(-len(data)%4)
    return out

def cpio_last(raw,want):
    pos=0;found=None
    while pos+110<=len(raw):
        if raw[pos:pos+6]!=b'070701':pos+=1;continue  # archive padding between members
        f=[int(raw[pos+6+i*8:pos+14+i*8],16) for i in range(13)];size,ns=f[6],f[11]
        name=raw[pos+110:pos+110+ns-1].decode();h=(110+ns+3)&~3
        if name==want:found=raw[pos+h:pos+h+size]
        pos+=h+((size+3)&~3)
    if found is None:raise ValueError('initrd lacks '+want)
    return found

def patch_tool_initrd(path,vendor_files,profile_dir):
    # Append a second gzip'd cpio member; the kernel unpacks it after the original and its files win.
    raw=gzip.decompress(path.read_bytes())
    # The initrd holds several concatenated cpio archives and the kernel keeps the LAST copy of a path.
    # (cpio -i stops at the first TRAILER, which is an older script without the graphics/shell rules.)
    script=cpio_last(raw,'payload/native_vendor_in_vm.py').decode()
    for old,new in VM_PATCHES:
        if script.count(old)!=1:raise ValueError('tool VM script patch anchor not found: '+old[:40])
        script=script.replace(old,new)
    extra=[]
    for e in vendor_files:
        d={'path':e['path'],'template':e['template']}
        if 'src' in e:
            data=(profile_dir/e['src']).read_bytes();d['data']=base64.b64encode(data).decode();d['sha256']=hashlib.sha256(data).hexdigest()
        else:d['copy_from']=e['copy_from']
        extra.append(d)
    member=cpio_newc([('payload/native_vendor_in_vm.py',0o100755,script.encode()),
                      ('payload/extra-vendor.json',0o100644,(json.dumps(extra,indent=1)+'\n').encode())])
    with path.open('ab') as f:f.write(gzip.compress(member,mtime=0))

def add_oem_file(image,src,dest,label):
    if not re.fullmatch(r'[a-z0-9_]+',label) or not re.fullmatch(r'/[A-Za-z0-9_./-]+',dest):raise ValueError('Unsafe oem file '+dest)
    if exists_in(image,dest):raise ValueError('Refusing to replace existing '+dest)
    parts=dest.split('/')[1:-1]
    for i in range(1,len(parts)+1):
        d='/'+'/'.join(parts[:i])
        if not exists_in(image,d):
            debugfs(image,'mkdir '+d,'sif %s mode 040755'%d,'sif %s uid 0'%d,'sif %s gid 0'%d,
                    'ea_set %s security.selinux u:object_r:%s:s0'%(d,label))
    debugfs(image,'write %s %s'%(src,dest),'sif %s mode 0100644'%dest,'sif %s uid 0'%dest,'sif %s gid 0'%dest,
            'ea_set %s security.selinux u:object_r:%s:s0'%(dest,label))

def replace_oem_text(image,path,old,new):
    # Rewrite one owned text file in compat.ext4, keeping mode, owner and SELinux label.
    with tempfile.TemporaryDirectory() as td:
        cur=pathlib.Path(td)/'cur';subprocess.run(['debugfs','-R','dump %s %s'%(path,cur),str(image)],check=True,capture_output=True,env=ENV)
        text=cur.read_text()
        if text.count(old)!=1:raise ValueError('%s: anchor not found exactly once'%path)
        ea=subprocess.run(['debugfs','-R','ea_get -V %s security.selinux'%path,str(image)],check=True,capture_output=True,text=True,env=ENV).stdout.strip()
        if not re.fullmatch(r'u:object_r:[a-z0-9_]+:s0',ea):raise ValueError('%s: unexpected label %r'%(path,ea))
        upd=pathlib.Path(td)/'new';upd.write_text(text.replace(old,new))
        debugfs(image,'rm '+path,'write %s %s'%(upd,path),'sif %s mode 0100644'%path,'sif %s uid 0'%path,'sif %s gid 0'%path,
                'ea_set %s security.selinux %s'%(path,ea))
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
    p.add_argument('--gki-modules',type=pathlib.Path,help='output directory of tools/build_gki_modules.py')
    p.add_argument('--firmware-cache',type=pathlib.Path,default=pathlib.Path('profile-firmware-cache'))
    a=p.parse_args();src=a.assets.resolve();out=a.output.absolute();profile=PROFILES[a.profile]
    if out.exists() or out.is_symlink():p.error('Output must not exist')
    if not shutil.which('debugfs') or not shutil.which('e2fsck'):p.error('Missing e2fsprogs (debugfs, e2fsck)')
    manifest=json.loads((src/'native-assets.json').read_text())
    for n,h in manifest['files'].items():
        if sha(src/n)!=h:raise ValueError('Source asset hash mismatch: '+n)
    cache=a.firmware_cache.resolve();fetched=[(e,fetch(e,cache)) for e in profile['files']]
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
        for rel,label in profile.get('oem_files',[]):
            add_oem_file(tmp/'compat.ext4',PROFILE_DIR/a.profile/'oem'/rel,'/'+rel,label)
        if profile.get('vendor_files'):
            patch_tool_initrd(tmp/'tool-initrd.gz',profile['vendor_files'],PROFILE_DIR/a.profile)
        mods=profile.get('oem_modules',[])
        if mods and not a.gki_modules:raise ValueError('profile needs --gki-modules (tools/build_gki_modules.py output)')
        for m in mods:
            ko=a.gki_modules/m['file']
            if sha(ko)!=m['sha256']:raise ValueError('GKI module hash mismatch: %s'%ko)
            add_oem_file(tmp/'compat.ext4',ko,'/modules/'+m['file'],'vendor_file')
        if profile.get('init_binds') or mods:
            binds=''.join('    mount none %s %s bind\n'%(s,d) for s,d in profile.get('init_binds',[]))
            binds+=''.join('    insmod /oem/modules/%s\n'%m['file'] for m in mods)
            replace_oem_text(tmp/'compat.ext4','/init.gbrunch.rc',INIT_ANCHOR,INIT_ANCHOR+binds)
        if profile.get('logger_capture'):
            replace_oem_text(tmp/'compat.ext4','/gbrunch-logger.sh',LOGGER_ANCHOR,LOGGER_CAPTURE+LOGGER_ANCHOR)
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
