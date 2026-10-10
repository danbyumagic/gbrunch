#!/usr/bin/env python3
"""Admission change must preserve boot arguments and installer UUID remapping."""
import pathlib,sys,tempfile,subprocess,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from googlebook_boot_menu import render,command_line
CMD='rdinit=/init console=ttyS0,115200 loglevel=8 drm.debug=0 androidboot.boot_part_uuid=12345678-1234-1234-1234-123456789abc androidboot.init_rc=/oem/init.gbrunch.rc'
class MenuTests(unittest.TestCase):
 def test_identical_command_and_default_gate(self):
  cfg=render(CMD)
  self.assertEqual(command_line(cfg),CMD)
  self.assertEqual(cfg.count('linux /EFI/GBRUNCH/kernel '),1)
  self.assertIn('set default=0',cfg)
  self.assertIn('"$board_product" = "8C4F"',cfg)
  experimental=cfg.split("menuentry 'Experimental boot",1)[1].split("menuentry 'UEFI",1)[0]
  self.assertIn('gbrunch_boot',experimental);self.assertNotIn('smbios',experimental)
 def test_installer_uuid_remapping(self):
  cfg=render(CMD).replace('12345678-1234-1234-1234-123456789abc','87654321-4321-4321-4321-cba987654321')
  self.assertIn('androidboot.boot_part_uuid=87654321-4321-4321-4321-cba987654321',command_line(cfg))
 def test_reject_ambiguous_or_foreign_configs(self):
  with self.assertRaises(ValueError):command_line('linux /EFI/GBRUNCH/kernel root=/dev/sda')
  with self.assertRaises(ValueError):command_line(render(CMD)+'\nlinux /EFI/GBRUNCH/kernel '+CMD+' changed=1\n')
  with self.assertRaises(ValueError):render(CMD+'; reboot')
 def test_existing_menu_upgrade_backup_and_idempotence(self):
  old="menuentry 'Old HP' {\n linux /EFI/GBRUNCH/kernel "+CMD+'\n initrd /EFI/GBRUNCH/initrd.gz\n}\n'
  with tempfile.TemporaryDirectory() as d:
   path=pathlib.Path(d)/'grub.cfg';path.write_text(old)
   script=pathlib.Path(__file__).resolve().parents[1]/'tools/googlebook_boot_menu.py'
   for _ in range(2):subprocess.run([sys.executable,str(script),'--config',str(path)],check=True,stdout=subprocess.DEVNULL)
   self.assertEqual(path.with_name('grub.cfg.before-experimental').read_text(),old)
   self.assertEqual(path.read_text(),render(CMD))
if __name__=='__main__':unittest.main()
