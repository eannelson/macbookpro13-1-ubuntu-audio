# Provenance and licensing

Upstream: https://github.com/federal1970/macbookpro13-1-fedora
Pinned repository revision: `287ceb1749c85b31b0386dabf629249b3d4f6349`.
Original location: `audio/upstream/series-rfc-v1/`.

| Order | Original patch commit | Author |
| --- | --- | --- |
| 1 | `73ef732e24e076314b08d44519c942a756c0b5a9` | Michal Szpakowski <michi.szpakowski@gmail.com> |
| 2 | `6ba1142e885d8a1033d4472be945ace2d546de70` | Michal Szpakowski <michi.szpakowski@gmail.com> |
| 3 | `90b864f9c91b2312a63d63f3b9ac87beedc03a68` | Michal Szpakowski <michi.szpakowski@gmail.com> |

These are mail-patch identities, not newly created commits in this repository. All three files are preserved byte for byte from the owner's read-only upstream checkout, which matches the pinned remote revision. Original author, date, subject, commit messages, and any trailers remain untouched. The RFC series has no Signed-off-by trailers; none has been added. Upstream [NOTES](upstream-NOTES.md) is also retained verbatim, including its discussion of development assistance and human sign-off.

The Ubuntu compatibility patch was copied from the owner's read-only `~/macbook-audio-backup/ubuntu-7.0-compat.patch`. Its exact original is retained under `patches/reference/`. Patch 4 adds an explanatory preamble and normalizes only the two file headers to the Ubuntu source path; its tested diff body, including whitespace, is identical. The Ubuntu 7.0 compatibility adaptation and repository packaging were developed and validated by the project maintainer with assistance from OpenAI ChatGPT and Codex. The compatibility change replaces an unavailable Linux 7.0 GPIO helper with equivalent HDA GPIO verb writes. The resulting driver was compiled and tested on a MacBookPro13,1 running Ubuntu 26.04.1 LTS. This work does not claim authorship of the original upstream CS8409 patches.

Working source at `~/kernel-work/cs8409-ubuntu-build/hda/codecs/cirrus/`, its existing module, and the original source at `~/kernel-work/linux-source-7.0.0/` are read-only references. Builds use the matching packaged Ubuntu source archive rather than copying generated objects or binaries from these locations.

Linux CS8409 files retain their existing copyright notices and exact SPDX licenses: `cs8409.c` and `cs8409.h` are GPL-2.0-or-later, while `cs8409-tables.c` is GPL-2.0-only. See the [kernel licensing rules](https://www.kernel.org/doc/html/latest/process/license-rules.html) for the distinction. The GPL version 2 text in LICENSE is copied from the matching Linux source's `LICENSES/preferred/GPL-2.0`. New project scripts and tests are GPL-2.0-only. This repository does not assert a new license over unrelated upstream repository contents or firmware; no firmware is bundled. The upstream patches credit davidjo/snd_hda_macbookpro for register sequences derived from AppleHDA; that attribution is preserved in patch 3.
