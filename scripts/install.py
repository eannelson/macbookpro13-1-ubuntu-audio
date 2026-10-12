#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Manual, approval-gated install; never loads or unloads a module."""
import argparse, subprocess
from pathlib import Path
from common import ROOT, output, validate_artifact
from system import gate, install_override, check_hardware, check_signing

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', default='7.0.0-38-generic')
    p.add_argument('--artifact', type=Path)
    p.add_argument('--approve-system-changes', action='store_true')
    a = p.parse_args()
    gate(a)
    check_hardware()
    module = validate_artifact(a.artifact or ROOT / 'artifacts' / a.kernel, a.kernel)
    check_signing(module)
    install_override(module.absolute(), a.kernel)
if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as e:
        raise SystemExit(str(e) + '\nNo automatic cleanup or reboot. If a transaction started, review its record and run rollback before rebooting.')
