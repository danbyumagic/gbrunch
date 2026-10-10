#!/usr/bin/env python3
"""Text interface for one reviewed install; never automatically chooses a target."""
import pathlib,json,datetime,subprocess,traceback,sys,os
from dualboot_installer import identity,read_layout,SOURCE_GUIDS,make_plan,apply_plan

def main():
 session=pathlib.Path('/logs')/('install-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S'));session.mkdir()
 print('\nGBRUNCH experimental internal installer\n')
 standalone=pathlib.Path('/run/standalone-source-verified.json').exists()
 print(('Uses the locally assembled Lenovo recovery and V7 fixes on this USB.' if standalone else 'Copies your tested V7 external SSD.')+' Windows must already have unallocated space.\nWindows is not resized. The internal install starts with fresh Android data.\n')
 disks=[];sources=[];inspection_errors={}
 for node in sorted(pathlib.Path('/sys/class/block').iterdir()):
  if (node/'partition').exists() or node.name.startswith(('ram','dm-','md')) or (node.name.startswith('loop') and not standalone):continue
  path='/dev/'+node.name
  try:
   meta=identity(path);parts=read_layout(path)['parts'];disks.append(meta)
   by={p['name']:p for p in parts}
   if meta['usb'] and all(by.get(n,{}).get('guid')==g for n,g in SOURCE_GUIDS.items()):sources.append(meta)
  except Exception as exc:inspection_errors[path]=repr(exc);continue
 (session/'disk-inspection-errors.json').write_text(json.dumps(inspection_errors,indent=2)+'\n')
 for d in disks:print(f"{d['path']} | {d['bytes']/1e9:.1f} GB | {'USB' if d['usb'] else 'internal'} | serial {d['serial']!r}")
 if len(sources)!=1:raise ValueError('Exactly one verified Googlebook source is required. For standalone installation, connect only this installer USB.' if standalone else 'Connect exactly one working V7 Googlebook SSD, then reboot this installer.')
 source=sources[0]['path'];print('\nGooglebook source: '+source)
 target=input('Enter the INTERNAL destination disk shown above, or press Enter to cancel: ').strip()
 if not target:return
 if target not in {d['path'] for d in disks if not d['usb']}:raise ValueError('Choose an internal disk from the displayed list.')
 print('\nInspecting source and destination. No writes to either disk.\n')
 plan=make_plan(source,target,32);(session/'inspection-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
 print(f"Destination: {target} | serial {plan['target']['serial']!r}\n")
 print(f"Allocate {plan['required_bytes']/1e9:.2f} GB in unallocated space.\nCreate {len(plan['new_partitions'])} Googlebook partitions, including fresh 32 GiB Android data.\nExisting Windows partitions and Windows EFI files remain intact.\nA new Googlebook EFI entry is appended after the existing boot entries.\n")
 print('Partition plan:')
 for p in plan['new_partitions']:print(f"  {p['name']:27s} {p['bytes']/(1<<20):9.1f} MiB")
 token='INSTALL '+plan['plan_sha256'][:12]
 print('\nHave a current Windows backup before installing.\nTo perform this exact installation, type: '+token)
 answer=input('Confirmation (Enter cancels): ').strip()
 if answer!=token:print('Cancelled. No installation writes occurred.');return
 print('\nInstalling. Keep all drives connected and power attached.\n')
 result=apply_plan(plan,session/'operation',pathlib.Path('/installer'),answer)
 print('\nCopy and partition installation completed.\nWindows retains its boot priority.\n')
 if not result.get('uefi_entry_created'):print('UEFI entry registration needs attention. Preserve the logs; do not reinstall.')
 print(('Shut down, disconnect the installer USB, and select GBRUNCH' if standalone else 'Shut down, disconnect BOTH external drives, and select GBRUNCH')+' from the HP boot menu.\nYour existing external Googlebook SSD remains a separate fallback.\nLogs are on the installer USB in '+session.name)
 input('Press Enter to shut down: ')

if __name__=='__main__':
 try:main()
 except Exception as exc:
  print('\nStopped: '+str(exc));traceback.print_exc()
  try:
   with open('/logs/installer-error.txt','a') as f:traceback.print_exc(file=f)
  except OSError:pass
  input('\nPreserve the installer USB logs. Press Enter to shut down: ')
