#!/usr/bin/env python3
"""Package only the independent compatibility partition and owned logger source."""
import pathlib,json,hashlib,tarfile,shutil
R=pathlib.Path(__file__).resolve().parents[1]
def main():
    p=R/'build/logging-v2-patch'
    test=json.loads((R/'evidence/native-logger-v2.json').read_text())
    assert test['fat_logs_recovered'] and test['xe_first_stage_loaded'] and not test['kernel_panic']
    for src,dst in [(R/'build/compat-probe/compat.ext4',p/'gbrunch-logging-v2-compat.ext4'),
                    (R/'tools/android_persistlogs.sh',p/'android_persistlogs.sh'),
                    (R/'tools/build_compat_probe.py',p/'build_compat_probe.py')]:shutil.copyfile(src,dst)
    for n in ['logger-v2-failure-tests.json','native-logger-v2.json','native-logger-v2-fat-log-readback.json']:shutil.copyfile(R/'evidence'/n,p/n)
    image=p/'gbrunch-logging-v2-compat.ext4';assert image.stat().st_size==67108864
    manifest={'purpose':'persistent logger update only','target_partition':31,
              'partition_uuid':'4ab7c001-7400-4bab-b412-43cbd52b9fb1','bytes':67108864,
              'compat_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
              'google_system_partitions_changed':False,'contains_google_proprietary_recovery_bytes':False,
              'logger_failure_tests':'passed','android_qemu_fat_readback':'passed','physical_hp_logger_v2':'not yet tested',
              'files':{str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file() and f.name!='manifest.json'}}
    (p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    archive=R/'build/gbrunch-logging-v2-patch.tar.gz'
    with tarfile.open(archive,'w:gz') as t:
        for f in sorted(p.rglob('*')):
            if f.is_file():t.add(f,arcname='gbrunch-logging-v2-patch/'+str(f.relative_to(p)),recursive=False)
    with archive.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
    (R/'evidence/logger-v2-release.json').write_text(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':h,
          'filebin_bin':'gbrunch-logging-v2-'+h[:12],'target_partition':31,'verified_qemu_saved_logs':True},indent=2)+'\n')
    print(archive.stat().st_size,h)
if __name__=='__main__':main()
