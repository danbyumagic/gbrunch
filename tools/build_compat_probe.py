#!/usr/bin/env python3
"""VM-only independent compatibility partition on a QCOW2 recovery view.
Original partition extents and bytes stay in the read-only backing image.
Not an external-drive installer; disables data encryption for diagnosis only.
"""
import hashlib,json,os,pathlib,shutil,struct,subprocess,uuid,zlib
from inspect_recovery import gpt
ROOT=pathlib.Path(__file__).resolve().parents[1]
build=pathlib.Path(os.environ.get('GBRUNCH_COMPAT_BUILD_DIR',str(ROOT/'build/compat-probe'))).resolve()
assert str(build).startswith(str(ROOT/'build')+'/'),'Compatibility output must stay in the Work build directory'
build.mkdir(parents=True,exist_ok=True)
stage=build/'files'; stage.mkdir(exist_ok=True)
(stage/'logs').mkdir(exist_ok=True)
radio=ROOT/'downloads/hp-radio-firmware'
for name in ['iwlwifi-ma-b0-gf-a0-89.ucode','intel/ibt-0180-0041.sfi','intel/ibt-0180-0041.ddc']:
    dest=stage/'firmware'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(radio/name,dest)

local=ROOT/'tools/local'; env=os.environ.copy()
env['LD_LIBRARY_PATH']=str(local/'usr/lib/x86_64-linux-gnu')
q=ROOT/'build/qemu11'
base=ROOT/'downloads/ruby-recovery.raw'
# All paths written are owned build artifacts, never the recovery base.
key=ROOT/'extracted/cuttlefish-x86/com.android.hardware.keymint.rust_nonsecure/payload'
gate=ROOT/'extracted/cuttlefish-x86/com.android.hardware.gatekeeper.nonsecure/payload'
boot=ROOT/'extracted/cuttlefish-x86/com.android.hardware.boot/payload'
for donor,label in [(key,'keymint'),(gate,'gatekeeper'),(boot,'boot')]:
    for sub in ['bin','lib64']:
        if (donor/sub).exists(): shutil.copytree(donor/sub,stage/label/sub,dirs_exist_ok=True)
# Explicit imports suppress board and firmware actions before parsing.
exclude={'gscutil.rc','gscd.rc','gscutil-executor.rc','check_tpm_clear.rc',
'desktop-trusty_security_vm_launcher.rc','android.hardware.security.keymint-service.desktop_trusty_system_vm.rc',
'android.hardware.gatekeeper-service.trusty.rc','android.hardware.security.secretkeeper.trusty.desktop.rc',
'android.hardware.weaver-service.android-desktop.rc',
'fwupd.rc','android.hardware.boot-service.android-desktop.rc','init.fatcat.rc','init.ruby.rc',
'init.insmod.rc','init.get_variant.rc','init.set_power_symlinks.rc','init.set_pnp_config.rc',
'init.common.rc','recovery-refresh.rc','flashrom.rc','update_engine.rc','update_verifier.rc','desktop_kernel_max_rollforward_boot.rc','futility-executor.rc','fwtool.rc','vboot.rc','vpd.rc','init.regdom.rc'}
imports=['import /system/etc/init/hw/init.rc']
records=[]
for folder,prefix in [('system_a-files/system/etc/init','/system/etc/init'),
 ('system_ext_a-files/etc/init','/system_ext/etc/init'),('vendor_a-files/etc/init','/vendor/etc/init')]:
    for path in sorted((ROOT/'extracted/ruby'/folder).glob('*.rc')):
        records.append({'path':prefix+'/'+path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'excluded':path.name in exclude})
        if path.name not in exclude: imports.append('import '+prefix+'/'+path.name)
imports+=['import /product/etc/init','import /odm/etc/init']
patch=next(x.split('=',1)[1] for x in (ROOT/'extracted/ruby/vendor_a-files/build.prop').read_text().splitlines() if x.startswith('ro.vendor.boot_security_patch='))
rc='\n'.join(imports)+'''

on early-init
    write /sys/module/firmware_class/parameters/path /oem/firmware
    write /sys/module/drm/parameters/debug 0
    chmod 0644 /sys/module/firmware_class/parameters/path
    chmod 0644 /sys/module/drm/parameters/debug
    setprop vendor.hwc.drm.force_color_mode 7
    setprop vendor.hwc.drm.persistent_hdr false
    setprop vendor.hwc.drm.enable_color_pipeline false
    setprop vendor.hwc.use_log_gamma_lut false
    setprop qemu.sf.lcd_density 160
    setprop ro.vendor.boot_security_patch GBRUNCH_PATCH_LEVEL
    write /dev/kmsg "GBRUNCH: independent compatibility init loaded"
    mount none /oem/fstab.android-desktop /vendor/etc/fstab.android-desktop bind
    mount none /oem/framework-manifest.xml /system_ext/etc/vintf/manifest.xml bind
    mount none /oem/security-manifest.xml /vendor/etc/vintf/manifest/android.hardware.gatekeeper-service.trusty.xml bind
    mount none /oem/weaver-manifest.xml /vendor/etc/vintf/manifest/android.hardware.weaver-service.android-desktop.xml bind

service gbrunch.keymint /oem/keymint/bin/hw/android.hardware.security.keymint-service.nonsecure
    class early_hal
    user nobody
    setenv LD_LIBRARY_PATH /oem/keymint/lib64
    seclabel u:r:hal_keymint_default:s0
    interface aidl android.hardware.security.keymint.IKeyMintDevice/default

service gbrunch.gatekeeper /oem/gatekeeper/bin/hw/android.hardware.gatekeeper-service.nonsecure
    class early_hal
    user system
    group system
    setenv LD_LIBRARY_PATH /oem/gatekeeper/lib64
    seclabel u:r:hal_gatekeeper_default:s0
    interface aidl android.hardware.gatekeeper.IGatekeeper/default

service gbrunch.boot /oem/boot/bin/hw/android.hardware.boot-service.default
    class early_hal
    user root
    group root
    seclabel u:r:hal_bootctl_default:s0
    interface aidl android.hardware.boot.IBootControl/default

on fs
    mount vfat /dev/block/by-name/GBLOG /oem/logs nosuid nodev noexec rw uid=2000,gid=2000,fmask=0077,dmask=0077,context=u:object_r:shell_data_file:s0
    start gbrunch.boot
    mount_all /oem/fstab.android-desktop --early

on late-fs
    mount_all /oem/fstab.android-desktop --late

service gbrunch.diagnostics /system/bin/sh -c "sleep 5; echo GBRUNCH_DIAGNOSTICS; id; service list; echo GBRUNCH_GRAPHICS_NODES; ls -l /dev/dri; echo GBRUNCH_GRAPHICS_LOG; logcat -b all -d -v threadtime -s minigbm cros_gralloc gralloc SurfaceFlinger drm_hwcomposer hwc3 EGL libEGL DEBUG linker"
    user shell
    group shell system log readproc
    seclabel u:r:shell:s0
    console ttyS0
    disabled
    oneshot

service gbrunch.persistlogs /system/bin/sh /oem/gbrunch-logger.sh
    capabilities SYSLOG
    user shell
    group shell system log readproc
    seclabel u:r:shell:s0
    disabled
    oneshot

on post-fs-data
    insmod /system/lib/modules/rfkill.ko
    insmod /system/lib/modules/pps_core.ko
    insmod /system/lib/modules/ptp.ko
    insmod /system/lib/modules/libarc4.ko
    insmod /vendor/lib/modules/cfg80211.ko
    insmod /vendor/lib/modules/iwlwifi.ko
    insmod /vendor/lib/modules/iwl7000_mac80211.ko
    insmod /vendor/lib/modules/iwlmvm.ko

on init
    chown root shell /dev/ttyS0
    chmod 0660 /dev/ttyS0

on boot
    start gbrunch.diagnostics
    start gbrunch.persistlogs
'''
rc=rc.replace('GBRUNCH_PATCH_LEVEL',patch)
(stage/'init.gbrunch.rc').write_text(rc)
shutil.copyfile(ROOT/'tools/android_persistlogs.sh',stage/'gbrunch-logger.sh')
fstab=(ROOT/'extracted/ruby/vendor_boot_a/fragment-0-platform-files/first_stage_ramdisk/fstab.android-desktop').read_text()
lines=[]
for line in fstab.splitlines():
    if 'voldmanaged=' in line:
        continue  # Experimental boot must not auto-mount other disks.
    if line.startswith('/dev/block/by-name/userdata '):
        fields=line.split()
        fields[4]=','.join(x for x in fields[4].split(',') if not x.startswith(('fileencryption=','keydirectory=')))
        line=' '.join(fields)
    lines.append(line)
lines.append('/dev/block/by-name/GBRUNCH /oem ext4 ro wait,first_stage_mount')
(stage/'fstab.android-desktop').write_text('\n'.join(lines)+'\n')
(stage/'framework-manifest.xml').write_text('''<manifest version="9.0" type="framework">
<hal format="hidl" max-level="8"><name>android.hidl.manager</name><transport>hwbinder</transport><fqname>@1.2::IServiceManager/default</fqname></hal>
<hal format="hidl" max-level="8"><name>android.hidl.token</name><transport>hwbinder</transport><fqname>@1.0::ITokenManager/default</fqname></hal>
</manifest>\n''')
# Do not advertise an unavailable Weaver service: LockSettings otherwise waits
# indefinitely on the main system_server thread and the watchdog restarts it.
# The original vendor fragment stays intact under this independent bind mount.
(stage/'weaver-manifest.xml').write_text('<manifest version="9.0" type="device"/>\n')
(stage/'security-manifest.xml').write_text('''<manifest version="9.0" type="device">
<hal format="aidl"><name>android.hardware.security.keymint</name><version>5</version><fqname>IKeyMintDevice/default</fqname></hal>
<hal format="aidl"><name>android.hardware.security.keymint</name><version>3</version><fqname>IRemotelyProvisionedComponent/default</fqname></hal>
<hal format="aidl"><name>android.hardware.security.secureclock</name><version>1</version><fqname>ISecureClock/default</fqname></hal>
<hal format="aidl"><name>android.hardware.security.sharedsecret</name><version>1</version><fqname>ISharedSecret/default</fqname><fqname>ISharedSecret/gatekeeper</fqname></hal>
<hal format="aidl"><name>android.hardware.gatekeeper</name><version>1</version><fqname>IGatekeeper/default</fqname></hal>
</manifest>\n''')
fs=build/'compat.ext4'
with fs.open('wb') as f: f.truncate(64*1024*1024)
subprocess.run([str(local/'usr/sbin/mke2fs'),'-q','-F','-t','ext4','-b','4096','-L','GBRUNCH','-d',str(stage),str(fs)],env=env,check=True)
# Preserve dedicated executable types; all other owned files are vendor_file.
cmd=[]
for path in [stage,*sorted(stage.rglob('*'))]:
    rel='/'+str(path.relative_to(stage)) if path!=stage else '/'
    label='vendor_file'
    if path.name in ['fstab.android-desktop','security-manifest.xml','weaver-manifest.xml']: label='vendor_configs_file'
    if path.name=='framework-manifest.xml': label='system_file'
    if '/firmware' in rel: label='vendor_firmware_file'
    if path.name=='gbrunch-logger.sh': label='shell_data_file'
    if path.name=='android.hardware.security.keymint-service.nonsecure': label='hal_keymint_default_exec'
    if path.name=='android.hardware.gatekeeper-service.nonsecure': label='hal_gatekeeper_default_exec'
    if path.name=='android.hardware.boot-service.default': label='hal_bootctl_default_exec'
    cmd.append(f'ea_set {rel} security.selinux u:object_r:{label}:s0')
    cmd.append(f'set_inode_field {rel} uid 0');cmd.append(f'set_inode_field {rel} gid 0')
    cmd.append(f'set_inode_field {rel} mode {"040755" if path.is_dir() else "0100755" if "/bin/" in rel else "0100644"}')
commands=build/'fs-metadata.commands'; commands.write_text('\n'.join(cmd)+'\n')
subprocess.run([str(local/'usr/sbin/debugfs'),'-w','-f',str(commands),str(fs)],env=env,check=True,stdout=subprocess.DEVNULL)
# Extend GPT metadata in the QCOW2 view; retain every original partition GUID/extent.
with base.open('rb') as f:
    original_partitions=gpt(f)
    f.seek(0)
    mbr=bytearray(f.read(512)); h=bytearray(f.read(512))
    table_lba,count,entry_size=struct.unpack_from('<QII',h,72)
    f.seek(table_lba*512); table=bytearray(f.read(count*entry_size))
slot=next(i for i in range(count) if not any(table[i*entry_size:i*entry_size+16]))
start=(base.stat().st_size+1048575)//1048576*2048
end=start+fs.stat().st_size//512-1
table_sectors=(len(table)+511)//512
last=end+table_sectors+1
entry=bytearray(entry_size)
entry[:16]=uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le
entry[16:32]=uuid.UUID('4ab7c001-7400-4bab-b412-43cbd52b9fb1').bytes_le
struct.pack_into('<QQQ',entry,32,start,end,0); entry[56:70]='GBRUNCH'.encode('utf-16le')
table[slot*entry_size:(slot+1)*entry_size]=entry
struct.pack_into('<Q',h,32,last);struct.pack_into('<Q',h,48,end)
struct.pack_into('<I',h,88,zlib.crc32(table));struct.pack_into('<I',h,16,0)
struct.pack_into('<I',h,16,zlib.crc32(h[:struct.unpack_from('<I',h,12)[0]]))
bh=bytearray(h);struct.pack_into('<QQ',bh,24,last,1);struct.pack_into('<Q',bh,72,last-table_sectors)
struct.pack_into('<I',bh,16,0);struct.pack_into('<I',bh,16,zlib.crc32(bh[:struct.unpack_from('<I',bh,12)[0]]))
struct.pack_into('<I',mbr,458,min(last,0xffffffff))
view=build/'recovery-view.qcow2'
if view.exists(): view.unlink()
subprocess.run([str(q/'qemu-img'),'create','-f','qcow2','-F','raw','-b',str(base),str(view),str((last+1)*512)],check=True)
for name,offset,data in [('mbr',0,mbr),('header',512,h),('table',table_lba*512,table),('backup-table',(last-table_sectors)*512,table),('backup-header',last*512,bh)]:
    path=build/(name+'.bin');path.write_bytes(data)
    subprocess.run([str(q/'qemu-io'),'-f','qcow2','-c',f'write -s {path} {offset} {len(data)}',str(view)],check=True,stdout=subprocess.DEVNULL)
subprocess.run([str(q/'qemu-io'),'-f','qcow2','-c',f'write -s {fs} {start*512} {fs.stat().st_size}',str(view)],check=True,stdout=subprocess.DEVNULL)
manifest={'status':'VM-only experimental compatibility partition; not HP-ready','base':'unchanged read-only official recovery','compat_partition_start':start*512,'compat_partition_bytes':fs.stat().st_size,'compat_sha256':hashlib.sha256(fs.read_bytes()).hexdigest(),'disk_view':str(view),'imports':records,'data_encryption':'disabled only for this diagnostic probe','software_security':'processes selected; full VINTF/policy/credential integration remains unproven', 'original_partition_count':len(original_partitions)}
(build/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:v for k,v in manifest.items() if k!='imports'},indent=2))
