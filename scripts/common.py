# SPDX-License-Identifier: GPL-2.0-only
import hashlib, json, os, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MODULE = 'snd-hda-codec-cs8409.ko'
UPSTREAM = '287ceb1749c85b31b0386dabf629249b3d4f6349'
def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)
def output(args):
    return run(args, capture_output=True, text=True).stdout.strip()
def supported(kernel):
    data = json.loads((ROOT / 'config/supported-kernels.json').read_text())
    if kernel not in data:
        raise ValueError('Unsupported kernel: ' + kernel)
    return data[kernel]
def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def verify_patches():
    expected = {}
    for line in (ROOT / 'patches/SHA256SUMS').read_text().splitlines():
        sha, name = line.split('  ', 1)
        path = ROOT / 'patches' / name
        if path.resolve().parent not in [(ROOT / 'patches').resolve(), (ROOT / 'patches/upstream').resolve(), (ROOT / 'patches/reference').resolve()]:
            raise ValueError('Unsafe patch path')
        if digest(path) != sha:
            raise ValueError('Patch checksum mismatch: ' + name)
        expected[name] = sha
    series = (ROOT / 'patches/series').read_text().splitlines()
    canonical = sorted(p for p in expected if p.startswith('upstream/')) + ['0004-ubuntu-7.0-gpio-compat.patch']
    if series != canonical or len(series) != 4 or any(p not in expected for p in series):
        raise ValueError('Invalid patch series')
    return {p: expected[p] for p in series}
def validate_artifact(directory, kernel):
    supported(kernel)
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    module = directory / MODULE
    if manifest['kernel'] != kernel or manifest['module_sha256'] != digest(module):
        raise ValueError('Artifact kernel or checksum mismatch')
    cfg = supported(kernel)
    if (manifest['source_package'] != cfg['source_package']
            or manifest['source_version'] != cfg['source_version']
            or manifest['source_archive_sha256'] != cfg['source_archive_sha256']
            or manifest['upstream_commit'] != UPSTREAM
            or manifest['patches'] != verify_patches()):
        raise ValueError('Artifact provenance mismatch')
    if output(['modinfo', '-F', 'vermagic', module]).split()[0] != kernel:
        raise ValueError('Module vermagic mismatch')
    if output(['modinfo', '-F', 'name', module]) != 'snd_hda_codec_cs8409':
        raise ValueError('Unexpected module name')
    if output(['modinfo', '-F', 'license', module]) != 'GPL':
        raise ValueError('Unexpected module license')
    return module
