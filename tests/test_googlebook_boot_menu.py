#!/usr/bin/env python3
"""Admission change must preserve boot arguments and installer UUID remapping."""
import pathlib,sys,tempfile,subprocess,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from googlebook_boot_menu import render,command_line,smbios_gate,PROFILES
CMD='rdinit=/init console=ttyS0,115200 loglevel=8 drm.debug=0 androidboot.boot_part_uuid=12345678-1234-1234-1234-123456789abc androidboot.init_rc=/oem/init.gbrunch.rc'
# Same command line with the Dragonfly profile options (prepare_profile_assets cmdline_append).
DF_CMD=CMD.replace(' androidboot.init_rc=',' xe.enable_psr=0 xe.enable_dpt=0 xe.enable_fbc=0 snd_intel_dspcfg.dsp_driver=3 androidboot.init_rc=')
ALL_REQUIRED=CMD+' '+' '.join(r for v in PROFILES for r in v.get('requires',[]))
class MenuTests(unittest.TestCase):
 def test_identical_command_and_default_gate(self):
  cfg=render(CMD)
  self.assertEqual(command_line(cfg),CMD)
  self.assertEqual(cfg.count('linux /EFI/GBRUNCH/kernel '),1)
  self.assertIn('set default=0',cfg)
  self.assertIn('"$board_product" = "8C4F"',cfg)
  # A build without the Dragonfly kernel options must not admit it by default (black panel).
  self.assertNotIn('"$board_product" = "8B63"',cfg)
  df=render(DF_CMD)
  self.assertEqual(command_line(df),DF_CMD)
  self.assertIn('"$board_product" = "8B63"',df)
  self.assertIn('"$system_product" = "HP Dragonfly 13.5 inch G4 Notebook PC"',df)
  experimental=cfg.split("menuentry 'Experimental boot",1)[1].split("menuentry 'UEFI",1)[0]
  self.assertIn('gbrunch_boot',experimental);self.assertNotIn('smbios',experimental)
 def test_amd_entry_is_opt_in_and_uses_separate_guarded_assets(self):
  self.assertNotIn("Experimental AMD",render(CMD))
  cfg=render(CMD,amd=True)
  self.assertEqual(command_line(cfg),CMD)
  self.assertIn("set default=0",cfg)
  self.assertIn("menuentry 'Experimental AMD (untested)'",cfg)
  self.assertIn("/EFI/GBRUNCH-AMD/profile-ready",cfg)
  self.assertIn("linux /EFI/GBRUNCH-AMD/kernel",cfg)
  self.assertIn("androidboot.init_rc=/oem/init.gbrunch-amd.rc",cfg)
  self.assertIn("drm.debug=0x1e",cfg)
 def test_profile_gate_is_exact_and_nested(self):
  gate=smbios_gate(ALL_REQUIRED)
  # Every profile requires vendor, product and board together; no partial matches.
  for v in PROFILES:
   block=gate.split('"$system_product" = "%s"'%v['product'],1)[1].split(' fi\n',1)[0]
   self.assertIn('"$board_product" = "%s"'%v['board'],block)
  self.assertEqual(gate.count('set allowed=1'),len(PROFILES)+1)
  lines=[l.strip() for l in gate.splitlines()]
  self.assertEqual(lines.count('fi'),sum(l.startswith('if [') for l in lines))
 def test_unsafe_profile_value_rejected(self):
  PROFILES.append({'name':'x','status':'profile','vendor':'HP','product':'bad"; reboot','board':'0000'})
  try:
   with self.assertRaises(ValueError):smbios_gate(CMD)
  finally:PROFILES.pop()
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
