#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import argparse
from common import supported, verify_patches, validate_artifact
p = argparse.ArgumentParser(description='Read-only validation; never loads modules')
p.add_argument('--kernel', default='7.0.0-38-generic')
p.add_argument('--artifact')
a = p.parse_args()
try:
    supported(a.kernel)
    verify_patches()
    if a.artifact:
        validate_artifact(a.artifact, a.kernel)
except (ValueError, OSError) as e:
    raise SystemExit(str(e))
print('Validation passed')
