# Nonprivileged build

Required tools: Python 3.12 or newer, make, patch, a compiler matching the Ubuntu kernel build toolchain, binutils, kmod (`modinfo`), dpkg tools, and the prepared Ubuntu headers for `7.0.0-38-generic` including `Module.symvers`. Missing prerequisites must be installed separately by the user; these scripts never install packages.

The installed source route checks `dpkg-query` for `linux-source-7.0.0` version `7.0.0-38.38`, then reads `/usr/src/linux-source-7.0.0.tar.bz2`. Alternatively:

```sh
python3 scripts/build.py --source-deb /path/to/linux-source-7.0.0_7.0.0-38.38_all.deb
```

The supplied package's name and version are checked before extracting its archive. The archive must also match the SHA-256 pinned in the allowlist, captured from the matching Ubuntu package on the reference machine. Installed header package versions and the amd64 architecture are checked. Only use packages from a trusted Ubuntu archive. To request an unprivileged download of that exact version using existing trusted apt metadata:

```sh
python3 scripts/build.py --download-source
```

This runs `apt-get download`, not `apt-get install` or `apt-get update`. If the version is unavailable, stop; do not substitute another version. No download happens without the flag. A local .deb's metadata check is not a cryptographic authenticity check.

The build extracts HDA files into a new private `build/cs8409-*` directory, verifies patch checksums, applies all four patches in order with zero fuzz, and replaces only the private cirrus Makefile with a CS8409-only external-module target. It uses the installed prepared headers with `make ... M=... modules`, following [kernel external-module documentation](https://docs.kernel.org/kbuild/modules.html). Header `include/config/kernel.release` is checked against the allowlist; Ubuntu's Makefile `kernelrelease` target can report the upstream base release instead of the Ubuntu ABI string.

Build directories and logs are retained for troubleshooting. The artifact manifest records the source archive SHA-256, source package version, upstream commit, patch hashes, compiler, target kernel, and module SHA-256. `modinfo` checks the module name, license, and vermagic without loading it. Only one `.ko` may be produced. Existing artifact directories are not overwritten; move a previous artifact aside manually before rebuilding.

This is a reproducible source-to-module procedure, not a claim of byte-for-byte reproducibility across compiler versions, paths, build timestamps or signing configurations. Inspect compiler warnings and retain your build log. The existing patched source and compiled module are read-only comparison references, never build inputs.
