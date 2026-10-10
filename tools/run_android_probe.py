#!/usr/bin/env python3
"""Boot original Android init in QEMU with an immutable recovery base.
No network, passthrough or host device access; disk writes go to a disposable
QEMU snapshot. Ramdisk additions belong to the separate experimental layer.
"""
import argparse, gzip, hashlib, json, os, pathlib, shutil, subprocess, time, threading
ROOT = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--seconds', type=int, default=45)
parser.add_argument('--name', default='android-probe')
parser.add_argument('--qemu', choices=['10', '11', 'patched'], default='11')
parser.add_argument('--compat', action='store_true', help='VM-only separate compatibility partition')
parser.add_argument('--vendor-view', action='store_true', help='Independent local-only vendor/policy view; requires --compat')
parser.add_argument('--native-gpu', action='store_true', help='Test original Xe first-stage loading; requires independent vendor view')
parser.add_argument('--guest-command', help='Diagnostic command sent to guest UART after 45 seconds')
a = parser.parse_args()
assert 1 <= a.seconds <= 600
assert a.name.replace('-', '').isalnum()
build = ROOT/'build/android-probe'; build.mkdir(parents=True, exist_ok=True)
ram = ROOT/'extracted/ruby'
cpio = (ram/'vendor_boot_a/fragment-0-platform.cpio').read_bytes()
cpio += (ram/'vendor_boot_a/fragment-2-dlkm.cpio').read_bytes()
cpio += (ram/'init_boot_a/ramdisk.cpio').read_bytes()
# Override unnecessary board-specific early module loads. NVMe is built in.
name = b'lib/modules/modules.load\0'; data = b'# GBRUNCH QEMU NVMe: no board-specific early modules\n'
fields = [900000, 0o100644, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name), 0]
h = b'070701'+b''.join(f'{n:08x}'.encode() for n in fields)+name
h += bytes(-len(h)%4); h += data+bytes(-len(data)%4)
name = b'TRAILER!!!\0'
fields = [900001, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, len(name), 0]
t = b'070701'+b''.join(f'{n:08x}'.encode() for n in fields)+name
cpio += h+t+bytes(-len(t)%4)
if a.compat:
    assert a.qemu == 'patched', 'Compatibility probe requires tested instruction emulation'
    name=b'first_stage_ramdisk/fstab.android-desktop\0'
    if a.vendor_view:
        data=(ROOT/'build/vendor-view/fstab.android-desktop').read_bytes()
    else:
        data=(ROOT/'build/compat-probe/files/fstab.android-desktop').read_bytes()
    fields=[900002,0o100644,0,0,1,0,len(data),0,0,0,0,len(name),0]
    h=b'070701'+b''.join(f'{n:08x}'.encode() for n in fields)+name
    h+=bytes(-len(h)%4); h+=data+bytes(-len(data)%4)
    cpio+=h+t+bytes(-len(t)%4)
initrd = build/'normal-initrd.gz'
if a.native_gpu:
    assert a.vendor_view and a.compat and a.qemu=='patched'
    initrd=ROOT/'build/native-android-gpu/initrd.gz'
    assert initrd.exists(), 'Run prepare_native_android_gpu.py first'
else:
    initrd.write_bytes(gzip.compress(cpio, mtime=0))
vbmeta = (ram/'vbmeta_a.img').read_bytes()
size = 256+int.from_bytes(vbmeta[12:20], 'big')+int.from_bytes(vbmeta[20:28], 'big')
digest = hashlib.sha256(vbmeta[:size]).hexdigest()
parts = json.loads((ram/'gpt.json').read_text())
boot_uuid = next(p['guid'] for p in parts if p['name']=='boot_a')
cmdline = ' '.join([
    'console=ttyS0,115200', 'earlycon=uart8250,io,0x3f8,115200', '8250.nr_uarts=4',
    'panic=0', 'root=/dev/ram0', 'loglevel=7', 'printk.devkmsg=on',
    'androidboot.init_log_level=debug',
    'androidboot.hardware=android-desktop', 'androidboot.hardware.platform=android-desktop',
    'androidboot.slot_suffix=_a', 'androidboot.force_normal_boot=1',
    'androidboot.boot_devices=pci0000:00/0000:00:03.0',
    f'androidboot.boot_part_uuid={boot_uuid}',
    f'androidboot.vbmeta.size={size}', 'androidboot.vbmeta.hash_alg=sha256',
    f'androidboot.vbmeta.digest={digest}', 'androidboot.vbmeta.device_state=unlocked',
    'androidboot.verifiedbootstate=orange', 'androidboot.veritymode=enforcing',
    'androidboot.hypervisor.protected_vm.supported=0',
    'androidboot.vendor.apex.com.android.hardware.keymint.strongbox.desktop=none',
])
if a.compat:
    cmdline+=' androidboot.init_rc=/oem/init.gbrunch.rc'
q = ROOT/('tools/qemu11' if a.qemu in ['11', 'patched'] else 'tools/qemu'); env = os.environ.copy()
env['LD_LIBRARY_PATH'] = str(q/'usr/lib/x86_64-linux-gnu')
env['QEMU_MODULE_DIR'] = str(q/'usr/lib/x86_64-linux-gnu/qemu')
env['TMPDIR'] = str(build)
prefix = [str(q/'usr/bin/qemu-system-x86_64')]
if a.qemu == 'patched':
    env.pop('LD_LIBRARY_PATH', None)
    prefix = [str(ROOT/'build/qemu11/qemu-system-x86_64')]
elif a.qemu == '11':
    prefix = [str(q/'usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'),
        '--library-path', str(q/'usr/lib/x86_64-linux-gnu'), *prefix]
disk = ROOT/('build/compat-probe/recovery-view.qcow2' if a.compat else 'downloads/ruby-recovery.raw')
if a.vendor_view:
    assert a.compat and a.qemu=='patched'
    disk=ROOT/'build/vendor-view/recovery-vendor-view.qcow2'
disk_format = 'qcow2' if a.compat else 'raw'
args = [*prefix, '-L', str(q/'usr/share/qemu'),
    '-machine', 'q35', '-accel', 'tcg', '-cpu', 'max', '-m', '4096', '-smp', '4',
    '-vga', 'none', '-display', 'none', '-serial', 'stdio', '-monitor', 'none',
    '-net', 'none', '-no-reboot', '-bios', str(q/'usr/share/seabios/bios-256k.bin'),
    '-kernel', str(ram/'boot_a/kernel'), '-initrd', str(initrd), '-append', cmdline,
    '-drive', f'if=none,id=os,format={disk_format},snapshot=on,file={disk}',
    '-device', 'nvme,drive=os,serial=GBRUNCHANDROID,addr=03.0']
log_path = ROOT/'evidence'/(a.name+'.log')
started = time.monotonic()
with log_path.open('wb') as log:
    p = subprocess.Popen(args, env=env, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
    def send_uart(data):
        try:
            if p.poll() is None: p.stdin.write(data.encode()); p.stdin.flush()
        except (BrokenPipeError, ValueError): pass
    timers=[]
    if a.guest_command:
        for delay,data in [(20,'\r'),(45,a.guest_command+'\r')]:
            timer=threading.Timer(delay,send_uart,args=(data,));timer.daemon=True;timer.start();timers.append(timer)
    try: code = p.wait(timeout=a.seconds); timed_out = False
    except subprocess.TimeoutExpired:
        p.terminate()
        try: code = p.wait(timeout=5)
        except subprocess.TimeoutExpired: p.kill(); code = p.wait()
        timed_out = True
    for timer in timers: timer.cancel()
    p.stdin.close()
output = log_path.read_text(errors='replace')
result = {'command': args, 'vbmeta_digest': digest, 'vbmeta_bytes': size,
    'duration_seconds': round(time.monotonic()-started, 2), 'exit_code': code,
    'timeout': timed_out, 'base_disk': 'immutable raw base + disposable QEMU snapshot',
    'log': str(log_path), 'guest_command': a.guest_command,
    'initrd_sha256': hashlib.sha256(initrd.read_bytes()).hexdigest()}
(ROOT/'evidence'/(a.name+'.json')).write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
