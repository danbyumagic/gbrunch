#!/usr/bin/env python3
"""Exercise empty output and command failures without Android or physical disks."""
import pathlib,tempfile,subprocess,os,json
R=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='gbrunch-logger-test-') as td:
    w=pathlib.Path(td);bindir=w/'bin';bindir.mkdir()
    def stub(n,s):
        p=bindir/n;p.write_text('#!/bin/sh\n'+s);p.chmod(0o755)
    stub('getprop','if [ ! -e "$MOCK_ROOT/prop-called" ]; then echo VALID_PROPERTIES; touch "$MOCK_ROOT/prop-called"; fi\n')
    stub('logcat','''case " $* " in
 *" -f "*) while [ "$1" != "-f" ]; do shift; done; shift; echo LIVE_LOG > "$1"; while :; do sleep 1; done;;
 *) if [ ! -e "$MOCK_ROOT/log-called" ]; then echo VALID_STARTUP_LOG; touch "$MOCK_ROOT/log-called"; fi;;
esac
''')
    stub('dumpsys','echo MOCK_DUMPSYS_FAILURE >&2; exit 124\n')
    stub('service','echo MOCK_SERVICE_LIST\n');stub('getenforce','echo Enforcing\n')
    stub('top','echo MOCK_TOP\n')
    stub('dmesg','echo avc: MOCK_KERNEL_AVC\n')
    stub('date','echo FIXED_TEST_TIME\n')
    source=(R/'tools/android_persistlogs.sh').read_text()
    source=source.replace('export PATH=/system/bin:/system/xbin','export PATH="'+str(bindir)+':/usr/bin:/bin"')
    source=source.replace('base=/oem/logs/Android-Logs','base="'+str(w/'logs')+'"')
    source=source.replace('/system/bin/timeout','/usr/bin/timeout').replace('01 02 03 04 05 06 07 08 09 10','01 02').replace('sleep 20','sleep 0')
    source=source.replace('-$$"','-fixed"')
    p=w/'logger.sh';p.write_text(source);env=os.environ.copy();env['MOCK_ROOT']=str(w)
    subprocess.run(['/bin/sh',str(p)],check=True,env=env,timeout=30)
    run=next((w/'logs').glob('run-*'));status=(run/'status.txt').read_text()
    assert (run/'startup-logcat.txt').read_text().strip()=='VALID_STARTUP_LOG'
    assert (run/'01-properties.txt').read_text().strip()=='VALID_PROPERTIES'
    assert not (run/'02-properties.txt').exists()
    assert 'EMPTY_CAPTURE 02-properties.txt' in status and 'exit=124' in status
    assert 'MOCK_DUMPSYS_FAILURE' in (run/'commands-stderr.txt').read_text()
    assert (run/'live-logcat.txt').read_text().strip()=='LIVE_LOG'
    assert 'LOGGER_COMPLETE' in status
    assert 'MOCK_KERNEL_AVC' in (run/'01-kernel-errors.txt').read_text()
    assert 'MOCK_TOP' in (run/'01-top.txt').read_text()
    assert (run/'01-process-labels.txt').stat().st_size>0
    subprocess.run(['/bin/sh',str(p)],check=True,env=env,timeout=30)
    assert len(list((w/'logs').glob('run-*')))==2
    assert (run/'startup-logcat.txt').read_text().strip()=='VALID_STARTUP_LOG'
    assert (run/'01-properties.txt').read_text().strip()=='VALID_PROPERTIES'
    stub('du','echo "25000 ignored"\n')
    subprocess.run(['/bin/sh',str(p)],check=True,env=env,timeout=30)
    assert len(list((w/'logs').glob('run-*')))==3
    assert any('BUDGET_SKIP' in (d/'status.txt').read_text() for d in (w/'logs').glob('run-*'))
    result={'capture_budget_skips_without_deleting_prior_logs':True,'earlier_nonempty_capture_retained':True,'empty_capture_does_not_overwrite':True,'command_failure_status_and_stderr_saved':True,'live_logging_separate':True,'repeated_clock_and_pid_do_not_overwrite_previous_boot':True}
    (R/'evidence/logger-v4-failure-tests.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
