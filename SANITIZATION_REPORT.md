# Sanitization Report: Family Creative Studio

**Date:** 2026-10-23

**Final index review:** 2026-10-23 14:40:23 UTC

**Auditor:** opensource-sanitizer v1.0.0 — independent review

**Verdict:** PASS

## Summary

| Category | Status | Findings |
|---|---|---|
| Secrets | PASS | 0 identified secrets; 2 independently resolved embedded-binary encoding matches |
| PII | PASS | 0 private personal identifiers found |
| Internal References | PASS | 0 private host, account, session, or home-directory references found |
| Dangerous Files | PASS | 0 staged dangerous files, symlinks, or submodules |
| Config Completeness | PASS | Public settings and internal-worker variables documented |
| Git History | PASS | Fresh unborn `main`; 0 historical commit objects, refs, or remotes at review |
| Third-party Retention | PASS | 7 selected files and 14 license/notice files independently checked against pinned upstream Git objects |

## Final Publication Scope

The completed publication index contains **92 files**: 91 text files, including this report, and one synthetic PNG preview. All staged text blobs were scanned regardless of extension. Staged contents were compared with their working-tree files; there were no differences and no nonignored untracked files at final review. `setup.sh` and the complete `web/` tree are included.

The scan covered hidden configuration examples, issue templates, source, tests, scripts, dependency manifests, vendored JavaScript with embedded WebAssembly, source provenance, public documentation, and the synthetic example. No private runtime or research files were scanned or copied into the review output.

The final index contains none of `.state/`, `.sources/`, `.venv/`, `node_modules/`, `dist/`, environment-secret files, private keys, credentials, sessions, source maps, dependency installations, bytecode, imported media, or private execution records. These local exclusions are reflected in `.gitignore` and were checked against the actual index rather than assumed from ignore rules.

The one staged image is `docs/images/preview.png`, a 1280×720 public synthetic assembly illustration. Its PNG chunks are only `IHDR`, `IDAT`, and `IEND`; there are no embedded textual, EXIF, or other ancillary metadata chunks. Packaging records its visual inspection against `examples/assembly.json`. This independent review verified its file structure and metadata; it does not claim a second independent visual inspection.

The sorted path-and-content SHA-256 of the 91 indexed files other than this report is `24cf9505f72903e308c419d9711b15f2bde759ac70094bb9d1895132348b585f`. Excluding the report avoids a self-referential digest.

This report describes the reviewed publication index before its initial commit. It does not claim a future commit hash or assert that subsequent changes have already been inspected.

## Critical Findings

None identified in the completed publication set.

## Warnings

None outstanding for the reviewed source-publication scope. The initial configuration warning was resolved: `.env.example` now documents `PYTHON_BIN` and explains that `STUDIO_CAD_MANIFEST` and `STUDIO_CAD_OUTPUT` are internal worker transport rather than user configuration.

## Independently Resolved Pattern Matches

Two AWS-access-key-shaped sequences occur at `vendor/pbakaus--impeccable/impeccable.js:3051`, inside the single `__IMPECCABLE_WASM_B64` string. The complete staged JavaScript matches the pinned upstream Git blob and the recorded SHA-256. The string decodes to a valid 2,118,168-byte WebAssembly module; no AWS-access-key-shaped byte string occurs in that decoded module. These are incidental Base64 matches, not identified credentials. No matched values are reproduced here.

No credential-bearing database URL, JWT, private key, GitHub token, Google OAuth secret, Slack webhook, SendGrid/Mailgun token, or identified API-key assignment was found. No personal-email pattern, private-IP pattern, numeric-host SSH command, private home path, or deployment identity was found. Public upstream author names, repository names, and the intended public repository owner remain intact.

## .env.example Audit

- Documented application overrides: `STUDIO_DATA`, `STUDIO_SOURCES`, `STUDIO_BROWSER`.
- Documented optional setup override: `PYTHON_BIN`.
- Documented internal worker variables: `STUDIO_CAD_MANIFEST`, `STUDIO_CAD_OUTPUT`; their values are assigned from worker arguments.
- Missing application configuration variables: none identified.
- Documented variables with no corresponding reference: none.
- Standard inherited operating-system variables and child settings assigned by the program are not secret input requirements.
- No Compose configuration is published.

## Source, Dependency, and License Checks

- All 12 source lock entries identify public GitHub HTTPS repositories and immutable 40-character commit IDs.
- All 7 remaining selected code/data files match their recorded vendored hashes. Their recorded original hashes independently match the named upstream Git blobs. Two files are explicitly marked as patched.
- All 14 retained original license/notice files independently match the named pinned upstream Git blobs. Original copyright and author notices are retained.
- The unused VoiceStudio/Patter helper and its associated notices are absent from the staged tree. The VoiceStudio lock entry selects no files and remains an optional research source. No VoiceStudio code or model weights are published in this checkout.
- The root MIT license and README describe project-owned work separately from retained third-party material. `THIRD_PARTY.md` preserves upstream license distinctions and accurately limits the integration claims.
- npm resolution URLs point to the public npm registry. No credential-bearing, private-host, or local-path dependency URL was found. The Python lock uses version pins.
- This is a source-publication and retained-notice audit, not a certification of every transitive dependency or model license. The publication contains no model weights or native executable release archives.

## Bootstrap and Added Runtime Review

The source bootstrap validates repository URL shape, checkout slug, full commit ID, and selected-file hashes. It checks out the fetched commit, verifies HEAD and cleanliness, and preserves a differing existing checkout instead of overwriting it. Git LFS smudging is disabled. Subprocess commands use argument arrays rather than shell interpolation.

The browser resolver locates a Chromium-family executable or accepts an explicit local `STUDIO_BROWSER` configuration. It does not execute a downloaded URL or accept this configuration from an unauthenticated network request. Relative worker paths are normalized before use. The doctor performs a bounded Bubblewrap capability test. The MCP smoke script uses a temporary synthetic data directory and does not require credentials.

`docs/SECURITY.md` accurately discloses the execution limits: network/PID isolation is not filesystem isolation, the host filesystem remains bound under the current account's permissions, and rendering Chromium uses `--no-sandbox`. Source publication does not authorize or imply deployment as a public multi-user service.

## Git History Audit

The index was inspected directly, including file modes and exact blob contents. It has no symlink, submodule, ignored runtime tree, or inherited project-history entry.

At review, `main` had no commits, no refs, and no remotes. An all-object type inventory found staged blob objects only and **zero commit objects**, confirming that historical secret-bearing commits were not inherited into the new repository. The initial commit can therefore contain the reviewed public tree without carrying the private workbench's history.

This audit did not create, stage, commit, or push files. Only `SANITIZATION_REPORT.md` was written by the auditor. The final report update is the sole expected working-tree change after review; publication should stage this report and preserve the reviewed file set.

## Recommendation

The reviewed publication set passes sanitization and retained-notice checks. Proceed with the initial public commit and push. Preserve the documented exclusions and the distinction between implemented functionality and unverified claims.
