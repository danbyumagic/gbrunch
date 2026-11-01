#!/usr/bin/env python3
"""Verify V8 changes only init.gbrunch.rc (two inserted lines), preserves every other V7 file and
label, and rebuilds to the same bytes.

  test_compat_v8.py [V7 compat.ext4]
"""
import importlib.util,pathlib,subprocess,sys,tempfile,json
R=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v8',R/'tools/build_compat_v8.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
v7=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else R/'build/compat-wifi-v7/compat.ext4'
debugfs,_,env=m.tools()
def invoke(image,cmd):return subprocess.check_output([debugfs,'-R',cmd,str(image)],env=env,stderr=subprocess.DEVNULL)
with tempfile.TemporaryDirectory() as td:
    t=pathlib.Path(td);a=m.build(v7,t/'a');b=m.build(v7,t/'b')
    assert a['v8_sha256']==b['v8_sha256']==m.sha(t/'a/compat.ext4'),'V8 is not reproducible'
    image=t/'a/compat.ext4';old=t/'old';new=t/'new';old.mkdir();new.mkdir()
    invoke(v7,f'rdump / {old}');invoke(image,f'rdump / {new}')
    oldfiles={str(p.relative_to(old)):p for p in old.rglob('*') if p.is_file()};newfiles={str(p.relative_to(new)):p for p in new.rglob('*') if p.is_file()}
    assert oldfiles.keys()==newfiles.keys()
    rc=m.RC.lstrip('/')
    for rel,p in oldfiles.items():
        if rel!=rc:assert p.read_bytes()==newfiles[rel].read_bytes(),rel
        assert invoke(v7,'ea_list /'+rel)==invoke(image,'ea_list /'+rel),rel
    before=oldfiles[rc].read_text().splitlines();after=newfiles[rc].read_text().splitlines()
    added=list(after)
    for line in before:added.remove(line)
    assert added==[l.rstrip('\n') for _,l in m.EDITS],added
    for anchor,line in m.EDITS:assert anchor+line in newfiles[rc].read_text()
    stat=invoke(image,'stat '+m.RC).decode();assert '0644' in stat and 'User:     0' in stat and 'Group:     0' in stat
    result=dict(v8_sha256=a['v8_sha256'],reproducible=True,other_v7_files_unchanged=len(oldfiles)-1,selinux_labels_unchanged=True,inserted_lines=added)
print(json.dumps(result,indent=2))
