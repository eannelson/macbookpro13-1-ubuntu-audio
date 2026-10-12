# Contributing

Run `make test` and `make validate` before proposing changes. Builds and tests must never load a module. Keep upstream patches unchanged and put local adaptations in separate patches. Preserve authorship, license notices and commit identities; do not add a sign-off on another person's behalf.

New kernel support requires an explicit reviewed allowlist entry, matching source package/version and headers, successful isolated build, and hardware validation. Record speaker, microphone, volume key, suspend/resume and headphone-switching results independently. A successful compile alone does not justify compatibility claims. Keep DKMS automation disabled until separately designed and approved.

Do not commit generated modules, kernel source trees, personal logs or machine identifiers. Do not push or publish changes without repository-owner approval. Report failures with target kernel, manifest, and sanitized build/runtime logs. Review install, rollback and recovery changes for preservation of the stock module and explicit approval gates.
