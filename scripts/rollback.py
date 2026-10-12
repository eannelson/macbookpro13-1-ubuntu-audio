#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Remove only this project's override; preserve stock and backup."""
import argparse, subprocess
from system import gate, rollback_override
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', default='7.0.0-38-generic')
    p.add_argument('--approve-system-changes', action='store_true')
    a = p.parse_args()
    gate(a)
    rollback_override(a.kernel)
if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as e:
        raise SystemExit(str(e) + '\nNo automatic cleanup or reboot. If a transaction started, review its record and run rollback before rebooting.')
