#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Separately approved recovery to the verified original manual override."""
import argparse
import subprocess
from system import gate
from migration import restore_manual

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', default='7.0.0-38-generic')
    p.add_argument('--approve-system-changes', action='store_true')
    a = p.parse_args()
    gate(a)
    restore_manual(a.kernel)
if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as e:
        raise SystemExit('\n'.join([str(e), *getattr(e, '__notes__', [])]) + '\nNo uncertain files automatically removed. Review the reported original/backup state before retrying.')
