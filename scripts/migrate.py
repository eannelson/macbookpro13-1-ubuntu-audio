#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Explicitly approved one-time migration of the pinned working manual override."""
import argparse
import subprocess
from pathlib import Path
from common import ROOT
from system import gate, check_hardware, check_signing
from migration import migrate, MigrationError

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', default='7.0.0-38-generic')
    p.add_argument('--artifact', type=Path)
    p.add_argument('--approve-system-changes', action='store_true')
    a = p.parse_args()
    gate(a)
    check_hardware()
    artifact = a.artifact or ROOT / 'artifacts' / a.kernel
    check_signing(artifact / 'snd-hda-codec-cs8409.ko')
    migrate(artifact, a.kernel)
if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError, MigrationError) as e:
        raise SystemExit(str(e))
