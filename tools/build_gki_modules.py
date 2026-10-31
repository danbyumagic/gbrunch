#!/usr/bin/env python3
"""Build out-of-tree modules for the stock Ruby GKI kernel (6.18.21-android17-5-g3938c8d97142-ab16302624).

Inputs (none are modified):
  --work     directory from prepare_amd_build_inputs.py --clang-only, plus source/ = git checkout of
             ACK 3938c8d97142d5cf31543aa96f864a2cf832dda0 (git verifies the tree; the Gitiles
             tarball is not byte-stable)
  --vmlinux  and --stock-modules  extracted from your own official recovery (for Module.symvers)
  --config   the recovery's embedded kernel config (extract-ikconfig)

Steps: apply the stock config. RUST is unavailable here, and the stock kernel was built with
RUST=y, so a one-line Kconfig change keeps CC_HAS_KCFI_ARITY/FINEIBT_BHI off as in the stock
kernel. Then fail unless the only config differences are Rust-only options. modules_prepare with
the stock KERNELRELEASE. Module.symvers comes from stock exports and the CRCs that stock modules
import (gki_symvers.py). Each module is built, stripped of debug info and build-id (byte-reproducible
across build paths), and every import is checked against that table.
"""
import argparse,hashlib,json,os,pathlib,re,shutil,subprocess,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import gki_symvers

SOURCE_COMMIT='3938c8d97142d5cf31543aa96f864a2cf832dda0'
RELEASE='6.18.21-android17-5-g3938c8d97142-ab16302624'
KCFI_LINE=('\tdepends on CC_IS_CLANG && !RUST\n','\tdepends on CC_IS_CLANG && !RUST && n  # GBRUNCH: stock kernel was built with RUST=y, so arity is off\n')
# Options that legitimately differ because no Rust toolchain is installed.
RUST_ONLY=re.compile(r'RUST|BINDGEN|NOVA|ASHMEM')
# name -> (files copied from the ACK tree, Kbuild text)
MODULES={
 'ac':(['drivers/acpi/ac.c'],'obj-m := ac.o\n'),
}

def run(*a,**k):return subprocess.run([str(x) for x in a],check=True,**k)

def config_lines(path):
    return {l.strip() for l in path.read_text().splitlines() if l.startswith(('CONFIG_','# CONFIG_'))}

def prepare(work,config,env):
    src,out=work/'source',work/'out'
    head=subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()
    if head!=SOURCE_COMMIT:raise SystemExit('source is not ACK '+SOURCE_COMMIT)
    kc=src/'arch/x86/Kconfig';t=kc.read_text()
    if KCFI_LINE[0] in t:kc.write_text(t.replace(KCFI_LINE[0],KCFI_LINE[1],1))
    elif KCFI_LINE[1] not in t:raise SystemExit('unexpected CC_HAS_KCFI_ARITY definition')
    out.mkdir(exist_ok=True);shutil.copyfile(config,out/'.config')
    mk=['make','-C',src,'O='+str(out),'LLVM=1','ARCH=x86_64','KERNELRELEASE='+RELEASE]
    run(*mk,'olddefconfig',env=env,stdout=subprocess.DEVNULL)
    diff=config_lines(config)^config_lines(out/'.config')
    bad=sorted(l for l in diff if not RUST_ONLY.search(l))
    if bad:raise SystemExit('config differs from stock beyond Rust options: '+'; '.join(bad))
    run(*mk,'-j%d'%os.cpu_count(),'modules_prepare',env=env,stdout=subprocess.DEVNULL)
    (out/'protected_module_names_list').write_text('')  # Android modpost input; no modules here are protected
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--work',required=True,type=pathlib.Path)
    p.add_argument('--vmlinux',required=True,type=pathlib.Path)
    p.add_argument('--stock-modules',nargs='+',required=True,type=pathlib.Path)
    p.add_argument('--config',required=True,type=pathlib.Path)
    p.add_argument('--output',required=True,type=pathlib.Path)
    p.add_argument('--modules',nargs='+',default=sorted(MODULES),choices=sorted(MODULES))
    a=p.parse_args();work=a.work.resolve();out_dir=a.output.resolve()
    clang=work/'clang-r584948c/bin'
    env=dict(os.environ,PATH=str(clang)+os.pathsep+os.environ['PATH'])
    want=[l for l in a.config.read_text().splitlines() if l.startswith('CONFIG_CC_VERSION_TEXT=')][0].split('=',1)[1].strip('"')
    have=subprocess.check_output([str(clang/'clang'),'--version'],text=True).splitlines()[0]
    if have!=want:raise SystemExit('compiler mismatch: %r != %r'%(have,want))
    out=prepare(work,a.config,env)
    symvers=out/'Module.symvers'
    sys.argv=['gki_symvers','--vmlinux',str(a.vmlinux),'--modules',*map(str,a.stock_modules),'--out',str(symvers)]
    gki_symvers.main()
    table={l.split('\t')[1]:int(l.split('\t')[0],16) for l in symvers.read_text().splitlines()}
    out_dir.mkdir(parents=True,exist_ok=True);manifest={'release':RELEASE,'source_commit':SOURCE_COMMIT,'compiler':have,'modules':[]}
    for name in a.modules:
        files,kbuild=MODULES[name];mdir=work/'mods'/name
        shutil.rmtree(mdir,ignore_errors=True);mdir.mkdir(parents=True)
        for f in files:shutil.copyfile(work/'source'/f,mdir/pathlib.Path(f).name)
        (mdir/'Kbuild').write_text(kbuild)
        log=run('make','-C',out,'LLVM=1','ARCH=x86_64','M='+str(mdir),'KERNELRELEASE='+RELEASE,'modules',env=env,capture_output=True,text=True)
        warn=[l for l in (log.stdout+log.stderr).splitlines() if 'WARNING' in l or 'ERROR' in l]
        if warn:raise SystemExit('%s: modpost warnings:\n%s'%(name,'\n'.join(warn)))
        for ko in sorted(mdir.glob('*.ko')):
            dest=out_dir/ko.name
            run(clang/'llvm-objcopy','--strip-debug','--remove-section=.note.gnu.build-id',ko,dest)
            imports=dict(gki_symvers.module_imports(dest))
            bad=[n for n,c in imports.items() if table.get(n)!=c]
            if bad:raise SystemExit('%s: import CRC not in stock table: %s'%(ko.name,bad))
            manifest['modules'].append({'file':ko.name,'sources':files,'imports':len(imports),
                                        'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size})
    (out_dir/'manifest.json').write_text(json.dumps(manifest,indent=1)+'\n')
    print(json.dumps(manifest['modules'],indent=1))

if __name__=='__main__':main()
