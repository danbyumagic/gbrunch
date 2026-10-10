#!/usr/bin/env python3
"""File-only QEMU integration, source and Windows fixtures stay private."""
import pathlib,subprocess,time,json,os
R=pathlib.Path(__file__).resolve().parents[1];B=R/'build/dualboot-installer';W=pathlib.Path('/tmp/gbrunch-installer-test');q=R/'tools/qemu';log=R/'evidence/installer-vm.log'
cmd=[str(R/'build/qemu11/qemu-system-x86_64'),'-L',str(q/'usr/share/qemu'),'-machine','q35','-accel','tcg','-cpu','qemu64','-m','1536','-smp','2','-display','none','-vga','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-bios',str(q/'usr/share/seabios/bios-256k.bin'),'-kernel',str(B/'linux-kernel'),'-initrd',str(B/'initrd.gz'),'-append','rdinit=/init console=ttyS0,115200 loglevel=4 gbrunch.fixture_tests=1','-drive',f'if=none,id=work,format=raw,file={W}/work.ext4,detect-zeroes=unmap,discard=unmap','-device','virtio-blk-pci,drive=work']
start=time.monotonic()
with log.open('wb') as f:
 p=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 try:code=p.wait(timeout=600)
 except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=10);raise RuntimeError('Installer tests timed out; inspect '+str(log))
s=log.read_text(errors='replace');print(s[-5000:]);require='INSTALLER_INTEGRATION_PASS' in s and 'INSTALLER_FIXTURE_TEST_EXIT=0' in s
report=dict(passed=require,seconds=round(time.monotonic()-start,2),exit_code=code,scope='real Linux/mtools/ext4/GPT installer on regular dummy disk fixtures; not Googlebook Android boot',physical_disks_accessed=False)
(R/'evidence/installer-vm-test.json').write_text(json.dumps(report,indent=2)+'\n');assert require,report
