# Sanitization Report: Family Creative Studio 0.3.0

**Date:** 2026-10-23

**Full publication scan:** 2026-10-23 19:02:32 UTC

**Final documentation delta review:** 2026-10-23 19:06:04 UTC

**Auditor:** opensource-sanitizer v1.0.0 — independent upgrade review

**Verdict:** PASS

## Summary

| Category | Status | Findings |
|---|---|---|
| Secrets | PASS | 0 identified secrets; 2 independently resolved embedded-binary encoding matches |
| PII | PASS | 0 private personal identifiers found |
| Internal References | PASS | 0 private deployment, account, session, or home-directory references found |
| Dangerous Files | PASS | 0 candidate dangerous files, symlinks, or submodules |
| Config Completeness | PASS | Application/setup settings and separate optional-test configuration documented |
| Git History | PASS | Existing public commit and all 92 historical blobs scanned; public origin contains no credentials |
| Third-party Retention | PASS | 7 selected code/data hashes and 14 license/notice files independently verified |

## Final Scope and Snapshot

The completed upgrade publication set contains **123 indexed files**: 122 text files, including this report, and one previously published synthetic PNG. There are no nonignored untracked files. All candidate text files were scanned regardless of extension, including source, tests, hidden configuration examples, issue templates, dependency manifests, vendored JavaScript, and final public documentation.

Every indexed file was compared with its working-tree contents. The only difference was this auditor-owned report, which is updated after the scan and must be staged by the release owner. No other code, documentation, or Git state was changed by the auditor.

The sorted path-and-content SHA-256 of the **122 publication files other than this report** is `3613670f74ead194aaf9c0f2636c7d366839ec9cfc94ce4ea9190e9aeb64a9bb`. Excluding the report avoids a self-referential digest. This identifies the reviewed upgrade payload, not a future commit hash.

The final pass includes README, both versioned verification JSON files, `docs/VERIFICATION.md`, `docs/REVIEW-RESOLUTION.md`, the portrait-layout corrections, the native-PPT background correction and its regression test. The historical `docs/verification-0.2.0.json` exactly matches the previous commit's verification JSON. The final delta review covered only `docs/VERIFICATION.md` and `docs/verification.json`, which added Mac viewer rebuild/context, synthetic-pixel and bundle-hash results. Both passed the same sanitization patterns; stored content hashes confirmed that every other reviewed payload file remained unchanged. These documentation checks do not independently re-run or certify the GPU measurements.

Ignored runtime/dependency trees and private review material were excluded. The actual index contains none of `.state/`, `.sources/`, `.venv/`, `node_modules/`, `dist/`, private media, runtime databases, environment-secret files, private keys, credential files, sessions, source maps, or operational logs. Credentials and private review directories were not read.

## Commands and Inspection Method

- `git status --short`, `git diff --stat HEAD` and targeted diffs identified upgrade changes.
- `git ls-files -z` and `git ls-files --others --exclude-standard -z` enumerated tracked and intended new publication files.
- `git ls-files --stage -z` and `git cat-file blob` checked index modes and exact staged contents against working files.
- Pattern scans covered API-key assignments, AWS identifiers/secrets, credential-bearing URLs, JWTs, private-key markers, GitHub/Google tokens, webhooks, private emails/IPs, SSH connections, home paths, deployment identifiers and high-entropy configuration assignments. Findings output contained categories, filenames and line numbers, not matched secret values.
- `git rev-list --all`, `git ls-tree -r -z` and `git cat-file` enumerated and scanned every reachable historical file blob. Commit author/committer addresses were classified without displaying personal values.
- Selected upstream files and license notices were independently compared with `git show <pinned-commit>:<source-path>` and SHA-256 checks.

No functional tests, new model consultations, source edits, Git staging, commits or pushes were performed by this audit. Functional acceptance belongs to the separately documented implementation verification.

## Critical Findings and Warnings

No identified critical finding or outstanding publication warning remains in the reviewed set.

The intended public GitHub owner, repository names and original upstream author/copyright notices are public attribution, not secrets. Localhost examples and reserved example-domain test fixtures do not identify private infrastructure.

Two AWS-access-key-shaped sequences occur at `vendor/pbakaus--impeccable/impeccable.js:3051`, inside its `__IMPECCABLE_WASM_B64` literal. The complete JavaScript matches the pinned upstream Git blob and recorded hash. Its Base64 decodes to a valid WebAssembly module; no AWS-shaped byte string occurs in the decoded module. These are incidental encoding matches, not identified credentials. No matched values are reproduced here.

The sole binary publication candidate, `docs/images/preview.png`, is unchanged from the previously published synthetic example. Its PNG chunks are only `IHDR`, `IDAT` and `IEND`, with no textual, EXIF or other ancillary metadata. This review verified bytes and metadata; it does not claim a new independent visual inspection.

## Configuration Audit

`.env.example` covers optional application/setup settings: `STUDIO_DATA`, `STUDIO_SOURCES`, `STUDIO_BROWSER` and `PYTHON_BIN`. The application does not load `.env` automatically.

The four optional test switches — `STUDIO_BROWSER_TESTS`, `STUDIO_PPT_INTEGRATION`, `STUDIO_PIPELINE_INTEGRATION` and `STUDIO_MEDIA_INTEGRATION` — are explicitly documented in `docs/VERIFICATION.md` with reproduction commands and their nonproduction scope. Keeping these in test documentation rather than `.env.example` does not omit required application configuration.

No Compose configuration is published. Standard inherited operating-system variables and program-assigned child settings are not additional secret-input requirements.

## Third-party Provenance and Licensing

All 7 selected code/data files match the current `vendor/sources.lock.json` hashes. Their recorded original hashes independently match the named files at the pinned upstream commits. All 14 retained license/NOTICE files match their upstream Git blobs.

The upgrade changes the vendored ArtCraft `HistoryManager.ts` and its lock hash to `3f4d744a19f336b63381a1afb50353755387d5354b3fc487bfb1f9f5e3e3ddff`. The original source hash remains recorded, the file remains marked as patched, and `THIRD_PARTY.md` describes its generation-aware queued-operation changes. No original license or notice was removed or rewritten.

The root MIT license is unchanged and applies to project-owned work; retained upstream MIT, Apache and dual-license distinctions remain explicit. VoiceStudio remains an optional research-only source with no selected code or model weights distributed in this checkout.

New direct declarations of `defusedxml` and `tinycss2` already have locked versions, `0.7.1` and `1.5.1`. npm resolution URLs use the public npm registry. No credential-bearing, private-host or local-path dependency URL was identified. Source commits and package artifact identity remain distinct in the documentation.

This verifies publication hygiene and retained attribution, not every transitive dependency's security or a comprehensive legal clearance of external tools and models.

## Existing Git History and Remote

This is an upgrade of an already published repository. At review, `git rev-list --all` found one existing public commit: `5fa508fb6ff0afee113f65c24b54d6c98eebd39b`. Its **92 unique historical blobs** — 91 text files and one PNG — were examined. The historical scan found no identified secrets or private references; its only token-shaped matches were the same resolved upstream WebAssembly encoding patterns.

Both author and committer use GitHub noreply addresses. The existing `origin` points to the intended public GitHub repository without embedded HTTPS credentials. This report does not claim the repository has no commits or remotes, and no history rewrite was performed.

## Recommendation

The reviewed 0.3.0 publication payload passes sanitization and notice-retention checks. Stage this updated report with the reviewed upgrade and proceed with the normal commit and push. Preserve the runtime/private-data exclusions. This PASS does not certify artistic superiority, runtime security isolation, or unreviewed future changes.
