#!/usr/bin/env python3
"""Summarize observed boot evidence without treating process launch as success."""
import argparse,json,pathlib,re
root=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('name');a=p.parse_args()
assert a.name.replace('-','').isalnum()
log=(root/'evidence'/(a.name+'.log')).read_text(errors='replace')
mounts={name:bool(re.search(r'__mount\(source=[^,]+,target=/'+name+r',type=erofs\)=0: Success',log)) for name in ['system','system_ext','product','vendor','vendor_dlkm','system_dlkm']}
independent_vendor='source=/dev/block/by-name/GBVENDOR,target=/vendor,type=erofs)=0: Success' in log
if independent_vendor:mounts['vendor']=False
r={'probe':a.name,'avb_handle_success':'Returning avb_handle with status: Success' in log,
   'original_erofs_mounts':mounts,'independent_vendor_mounted':independent_vendor,'second_stage_init':'init second stage started!' in log,
   'selinux_enforcing':'enforcing=1 old_enforcing=0' in log,
   'compat_partition_mounted':bool(re.search(r'__mount\(source=/dev/block/by-name/GBRUNCH,target=/oem,type=ext4\)=0: Success',log)),
   'compat_init_parsed':'Parsing file /oem/init.gbrunch.rc' in log,
   'userdata_mount_success':bool(re.search(r'__mount\(source=[^,]+,target=/data,type=ext4\)=0: Success',log)),
   'software_keymint_process_started':bool(re.search(r"started service 'gbrunch.keymint' has pid",log)),
   'software_gatekeeper_process_started':bool(re.search(r"started service 'gbrunch.gatekeeper' has pid",log)),
   'software_boot_control_registered':'IBootControl AIDL service running' in log,
   'apex_activated':'Marking APEXd as activated' in log,
   'zygote_process_started':bool(re.search(r"started service 'zygote' has pid",log)),
   'zygote_restarted_or_killed':bool(re.search(r"Service 'zygote'.*received SIG",log)),
   'surfaceflinger_process_started':bool(re.search(r"started service 'surfaceflinger' has pid",log)),
   'manifest_mount_denied':bool(re.search(r"mount none /oem/.*failed: mount\(\) failed: Permission denied",log)),
   'sharedsecret_manifest_missing':bool(re.search(r'Could not find android.hardware.security.sharedsecret',log)),
   'kernel_panic':'Kernel panic' in log,'unsupported_instruction_trap':'trap invalid opcode' in log,
   'guest_shell_marker':'GBRUNCH_GUEST_SHELL' in log,
   'uart_diagnostic_ran':'GBRUNCH_DIAGNOSTICS' in log,
   'software_services_observed_in_list':{name:bool(re.search(r'\d+\s+'+re.escape(name)+r':',log)) for name in ['android.hardware.gatekeeper.IGatekeeper/default','android.hardware.security.keymint.IKeyMintDevice/default','android.hardware.security.sharedsecret.ISharedSecret/default','android.hardware.security.sharedsecret.ISharedSecret/gatekeeper','android.system.keystore2.IKeystoreService/default']},
   'security_service_crash_observed':bool(re.search(r"Service '(?:gbrunch.keymint|gbrunch.gatekeeper|keystore2)'.*received SIG",log)),
   'limitations':'Process launch alone does not prove desktop, credentials, successful framework boot, or hardware compatibility.'}
out=root/'evidence'/(a.name+'-milestones.json');out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
