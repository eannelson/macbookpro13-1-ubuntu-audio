#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Nonprivileged, isolated module build; no installation or module loading."""
import argparse, json, os, shutil, tempfile, tarfile
from pathlib import Path
from common import ROOT, MODULE, UPSTREAM, run, output, supported, digest, verify_patches

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', default='7.0.0-38-generic')
    p.add_argument('--source-deb', type=Path, help='Matching Ubuntu linux-source .deb')
    p.add_argument('--download-source', action='store_true', help='Explicitly download exact source package with apt-get download (no install)')
    p.add_argument('--jobs', type=int, default=2)
    a = p.parse_args()
    cfg = supported(a.kernel)
    if os.geteuid() == 0:
        raise ValueError('Build as an ordinary user')
    if a.jobs < 1:
        raise ValueError('jobs must be positive')
    patches = verify_patches()
    if output(['dpkg', '--print-architecture']) != cfg['architecture']:
        raise ValueError('Unsupported architecture')
    for package in ['linux-headers-7.0.0-38', 'linux-headers-' + a.kernel]:
        if output(['dpkg-query', '-W', '-f=${Version}', package]) != cfg['source_version']:
            raise ValueError('Matching header package version required: ' + package)
    headers = Path('/lib/modules') / a.kernel / 'build'
    if not headers.is_dir() or not (headers / 'Module.symvers').is_file():
        raise ValueError('Matching prepared headers and Module.symvers required')
    if (headers / 'include/config/kernel.release').read_text().strip() != a.kernel:
        raise ValueError('Headers kernelrelease mismatch')
    ROOT.joinpath('build').mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='cs8409-', dir=ROOT / 'build'))
    print('Private build directory:', work, flush=True)
    if a.download_source:
        if a.source_deb:
            raise ValueError('Choose --source-deb or --download-source')
        run(['apt-get', 'download', cfg['source_package'] + '=' + cfg['source_version']], cwd=work)
        debs = list(work.glob('*.deb'))
        if len(debs) != 1:
            raise ValueError('Expected exactly one downloaded package')
        a.source_deb = debs[0]
    if a.source_deb:
        deb = a.source_deb.resolve()
        if output(['dpkg-deb', '-f', deb, 'Package']) != cfg['source_package'] or output(['dpkg-deb', '-f', deb, 'Version']) != cfg['source_version']:
            raise ValueError('Source package identity mismatch')
        run(['dpkg-deb', '-x', deb, work / 'package'])
        archive = work / 'package/usr/src' / cfg['source_archive']
    else:
        version = output(['dpkg-query', '-W', '-f=${Version}', cfg['source_package']])
        if version != cfg['source_version']:
            raise ValueError('Installed source package version mismatch; supply --source-deb')
        archive = Path('/usr/src') / cfg['source_archive']
    archive_sha = digest(archive)
    if archive_sha != cfg['source_archive_sha256']:
        raise ValueError('Source archive checksum mismatch')
    # Extract only HDA sources/private headers from the package, never use reference build products.
    with tarfile.open(archive) as tar:
        members = [m for m in tar.getmembers() if m.name.startswith('linux-source-7.0.0/sound/hda/')]
        for m in members:
            if m.issym() or m.islnk() or '..' in Path(m.name).parts or Path(m.name).is_absolute():
                raise ValueError('Unsafe source archive member')
        tar.extractall(work, members=members, filter='data')
    source = work / 'linux-source-7.0.0'
    for name in patches:
        run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', ROOT / 'patches' / name], cwd=source)
    module_dir = source / 'sound/hda/codecs/cirrus'
    (module_dir / 'Makefile').write_text('# SPDX-License-Identifier: GPL-2.0-only\nsubdir-ccflags-y += -I$(src)/../../common\nsnd-hda-codec-cs8409-y := cs8409.o cs8409-tables.o\nobj-m := snd-hda-codec-cs8409.o\n')
    run(['make', '-C', headers, 'M=' + str(module_dir), '-j' + str(a.jobs), 'modules'])
    modules = list(module_dir.glob('*.ko'))
    if [m.name for m in modules] != [MODULE]:
        raise ValueError('Build produced unexpected modules')
    artifact = ROOT / 'artifacts' / a.kernel
    if artifact.exists():
        raise ValueError('Artifact directory exists; move it aside before rebuilding: ' + str(artifact))
    artifact.mkdir(parents=True)
    shutil.copy2(modules[0], artifact / MODULE)
    manifest = {'kernel': a.kernel, 'source_package': cfg['source_package'], 'source_version': cfg['source_version'], 'source_archive_sha256': archive_sha, 'upstream_commit': UPSTREAM, 'patches': patches, 'module_sha256': digest(artifact / MODULE), 'compiler': output(['cc', '--version']).splitlines()[0]}
    (artifact / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    from common import validate_artifact
    validate_artifact(artifact, a.kernel)
    print('Validated artifact:', artifact)
if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as e:
        raise SystemExit(str(e))
