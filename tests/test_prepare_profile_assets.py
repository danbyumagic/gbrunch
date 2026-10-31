#!/usr/bin/env python3
"""Profile asset derivation on a synthetic kit: no network, no Google bytes, no block devices."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
os.environ['PATH']+=os.pathsep+'/sbin'+os.pathsep+'/usr/sbin'
import prepare_profile_assets as ppa

GRUB='''set timeout=10
set default=0
menuentry 'GBRUNCH experimental Googlebook Android + Intel Xe' {
 insmod smbios
 smbios --type=1 --get-string=4 --set=system_vendor
 smbios --type=1 --get-string=5 --set=system_product
 smbios --type=2 --get-string=5 --set=board_product
 set allowed=0
 if [ "$system_vendor" = "QEMU" ]; then
  set allowed=1
 fi
 if [ "$system_vendor" = "HP" ]; then
  if [ "$system_product" = "HP Envy x360 2-in-1 Laptop 15-fe1xxx" ]; then
   if [ "$board_product" = "8C4F" ]; then
    set allowed=1
   fi
  fi
 fi
 if [ "$allowed" = "1" ]; then
  linux /EFI/GBRUNCH/kernel CMDLINE
  initrd /EFI/GBRUNCH/initrd.gz
 else
  echo 'This experiment is restricted to the tested HP 15-fe1xxx / 8C4F or QEMU.'
  sleep 15
 fi
}
menuentry 'UEFI firmware settings' { fwsetup }
'''
sha=lambda b:hashlib.sha256(b).hexdigest()
TOOLS=all(shutil.which(t) for t in ['mke2fs','debugfs','e2fsck'])

@unittest.skipUnless(TOOLS,'e2fsprogs required')
class ProfileAssetTests(unittest.TestCase):
    def setUp(self):
        self.t=pathlib.Path(tempfile.mkdtemp(prefix='gbrunch-profile-test-'));kit=self.t/'kit';(kit/'licenses').mkdir(parents=True)
        (kit/'firmware/i915').mkdir(parents=True);(kit/'firmware/i915/old.bin').write_bytes(b'old')
        (kit/'native-grub.cfg').write_text(GRUB);(kit/'licenses/x.txt').write_text('x')
        root=self.t/'root';(root/'firmware/intel').mkdir(parents=True)
        subprocess.run(['mke2fs','-q','-t','ext4','-d',str(root),str(kit/'compat.ext4'),'8M'],check=True)
        files={str(f.relative_to(kit)):sha(f.read_bytes()) for f in kit.rglob('*') if f.is_file()}
        (kit/'native-assets.json').write_text(json.dumps({'scope':'test','cmdline':'rdinit=/init drm.debug=0 androidboot.init_rc=/oem/init.gbrunch.rc','firmware':[{'name':'i915/old.bin','sha256':sha(b'old'),'bytes':3}],'files':files}))
        cache=self.t/'cache'/ppa.COMMIT;entries=[]
        for name,target,data in [('i915/new.bin','initrd',b'gpu'),('wifi.ucode','oem',b'wifi'),('intel/bt.sfi','oem',b'bt'),('LICENCE.t','license',b'lic')]:
            (cache/name).parent.mkdir(parents=True,exist_ok=True);(cache/name).write_bytes(data)
            entries.append({'name':name,'target':target,'sha256':sha(data),'bytes':len(data)})
        self.saved=dict(ppa.PROFILES);ppa.PROFILES['test']={'board':'8B63','evidence':'synthetic','files':entries,'cmdline_append':'xe.enable_dpt=0'}
        self.kit=kit;self.before={k:sha((kit/k).read_bytes()) for k in files}
    def tearDown(self):
        ppa.PROFILES.clear();ppa.PROFILES.update(self.saved);shutil.rmtree(self.t)
    def run_tool(self,out):
        sys.argv=['x','--assets',str(self.kit),'--output',str(out),'--profile','test','--firmware-cache',str(self.t/'cache')];ppa.main()
    def test_derived_kit(self):
        out=self.t/'out';self.run_tool(out)
        m=json.loads((out/'native-assets.json').read_text())
        self.assertEqual([v['name'] for v in m['firmware']],['i915/old.bin','i915/new.bin'])
        self.assertEqual(m['cmdline'],'rdinit=/init drm.debug=0 xe.enable_dpt=0 androidboot.init_rc=/oem/init.gbrunch.rc')
        for n,h in m['files'].items():self.assertEqual(sha((out/n).read_bytes()),h,n)
        self.assertTrue((out/'licenses/LICENCE.t').is_file())
        for path,data in [('/firmware/wifi.ucode',b'wifi'),('/firmware/intel/bt.sfi',b'bt')]:
            dump=self.t/'dump';subprocess.run(['debugfs','-R','dump %s %s'%(path,dump),str(out/'compat.ext4')],check=True,capture_output=True)
            self.assertEqual(dump.read_bytes(),data)
            ea=subprocess.run(['debugfs','-R','ea_list '+path,str(out/'compat.ext4')],capture_output=True,text=True).stdout
            self.assertIn(ppa.FIRMWARE_LABEL,ea)
        cfg=(out/'native-grub.cfg').read_text()
        self.assertIn('"$board_product" = "8B63"',cfg);self.assertIn('"$board_product" = "8C4F"',cfg)
        self.assertIn('linux /EFI/GBRUNCH/kernel CMDLINE',cfg);self.assertNotIn('restricted to the tested HP',cfg)
        if shutil.which('grub-script-check'):subprocess.run(['grub-script-check',str(out/'native-grub.cfg')],check=True)
        self.assertEqual({k:sha((self.kit/k).read_bytes()) for k in self.before},self.before,'source kit modified')
    def test_refuses_existing_output_and_bad_firmware(self):
        out=self.t/'out';out.mkdir()
        with self.assertRaises(SystemExit):self.run_tool(out)
        (self.t/'cache'/ppa.COMMIT/'wifi.ucode').write_bytes(b'tampered')
        with self.assertRaises(ValueError):self.run_tool(self.t/'out2')
        self.assertFalse((self.t/'out2').exists());self.assertFalse((self.t/'out2.partial').exists())
    def test_tampered_source_kit_rejected(self):
        (self.kit/'licenses/x.txt').write_text('changed')
        with self.assertRaises(ValueError):self.run_tool(self.t/'out')

class PinnedProfileTests(unittest.TestCase):
    def test_dragonfly_pins(self):
        p=ppa.PROFILES['hp-dragonfly-g4'];names={e['name'] for e in p['files']}
        for n in ['i915/adlp_dmc.bin','i915/adlp_guc_70.bin','i915/tgl_huc.bin','iwlwifi-so-a0-gf-a0-89.ucode','iwlwifi-so-a0-gf-a0.pnvm','intel/ibt-0040-0041.sfi','intel/ibt-0040-0041.ddc']:
            self.assertIn(n,names)
        for e in p['files']:
            self.assertRegex(e['sha256'],'^[0-9a-f]{64}$')
            self.assertEqual(e['target']=='initrd',e['name'].startswith('i915/'))
    def test_installer_accepts_pinned_profile_image(self):
        import dualboot_installer
        self.assertEqual(dualboot_installer.COMPAT_HASH,ppa.BASE_COMPAT)
        for name,p in ppa.PROFILES.items():
            self.assertIn(p['compat_sha256'],dualboot_installer.COMPAT_HASHES,name)

if __name__=='__main__':unittest.main()
