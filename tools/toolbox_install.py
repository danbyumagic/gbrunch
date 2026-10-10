#!/usr/bin/env python3
"""Install from the verified locally built view; retain the existing installer guards."""
import pathlib,datetime,json,traceback,sys
from toolbox_source import local_source
from dualboot_installer import identity,read_layout,make_plan,apply_plan
def main():
 with local_source() as (source,w,parent):
  session=w/'logs'/('local-install-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S'));session.mkdir()
  print('Verified locally assembled Lenovo recovery + V7 compatibility. Windows must already have unallocated space. No Windows resizing. Fresh 32 GiB Android data.')
  targets=[]
  for node in sorted(pathlib.Path('/sys/class/block').iterdir()):
   if (node/'partition').exists() or node.name.startswith(('loop','nbd','ram','dm-','md')):continue
   try:
    d=identity('/dev/'+node.name)
    if not d['usb']:read_layout(d['path']);targets.append(d);print(f"{d['path']} | {d['bytes']/1e9:.1f} GB | serial {d['serial']!r}")
   except (OSError,ValueError):pass
  target=input('Enter an INTERNAL disk above, or Enter to cancel: ').strip()
  if not target:return
  if target not in {d['path'] for d in targets}:raise ValueError('Choose a listed internal disk')
  plan=make_plan(source,target,32);(session/'inspection-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
  print(f"Create {len(plan['new_partitions'])} Googlebook partitions in {plan['required_bytes']/(1<<30):.2f} GiB of unallocated space. Preserve existing Windows partitions and EFI files; retain Windows boot priority.")
  for p in plan['new_partitions']:print(f"  {p['name']:27s} {p['bytes']/(1<<20):9.1f} MiB")
  token='INSTALL '+plan['plan_sha256'][:12];answer=input('Type '+token+' to install, or Enter to cancel: ').strip()
  if answer!=token:print('Cancelled; no installation writes.');return
  result=apply_plan(plan,session/'operation',pathlib.Path('/opt/gbrunch/source'),answer)
  print('Installation verified. Shut down, disconnect the USB and select GBRUNCH from the HP boot menu. Logs: '+str(session))
  if not result.get('uefi_entry_created'):print('Boot registration needs attention; preserve logs and do not reinstall.')
if __name__=='__main__':
 rc=0
 try:main()
 except Exception:traceback.print_exc();rc=1
 input('Press Enter to close: ');sys.exit(rc)
