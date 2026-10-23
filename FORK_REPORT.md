# Public fork report: Family Creative Studio

Date: 2026-10-23

This public checkout was copied from a private development workbench using an explicit allowlist. The original workbench, user projects, imported media, runtime services, and private evidence were left untouched. The public checkout contains no inherited Git history.

## Initial copy

- 73 source, test, dependency, and third-party attribution files copied.
- Allowed trees: `studio/`, `web/`, `tests/`, and `vendor/`.
- Allowed top-level files: `pyproject.toml`, `requirements.lock.txt`, `package.json`, `package-lock.json`, and `THIRD_PARTY.md`.
- Runtime helpers retained: `scripts/build.mjs`, `scripts/anatomy.mjs`, and `scripts/glb-check.mjs`.
- No symbolic links copied. Generated bundles must be rebuilt from source.

## Excluded from the public copy

- Private runtime state: databases, user projects, imported assets, caches, sockets, and job output.
- Private research and operational material: advisor conversations, execution receipts, logs, screenshots, release backups, and historical acceptance evidence.
- Local deployment files: machine-specific service units, remote command wrappers, and deployment-specific documentation.
- Generated or installed files: virtual environments, dependency directories, compiled bundles, Python bytecode, and test caches.
- Demo and showcase links to private output directories.
- Environment files, credential files, private keys, sessions, and Git metadata.
- Development-only helper scripts tied to historical fixtures and private evidence directories.

These items were omitted from the new copy; nothing was deleted from the source workbench.

## Configuration and reference changes

Four copied files were modified during the initial fork:

1. `studio/paths.py`: the default runtime-source location is the checkout's `.sources/` directory; `STUDIO_SOURCES` can override it.
2. `vendor/sources.lock.json`: twelve machine-specific source roots are represented as relative `.sources/<slug>` paths. Repository URLs, pinned commits, license fields, and selected-file hashes are preserved.
3. `web/app.js`: the deployment-machine label is replaced by a generic local-studio label.
4. `THIRD_PARTY.md`: private machine/research/evidence references are removed or described through public tests. Third-party license distinctions remain explicit.

Sixteen deployment identity/path references were replaced, and two references to private evidence were replaced by public-test descriptions. No application behavior was otherwise changed in this fork stage.

`.env.example` was generated with two optional configuration variables (`STUDIO_SOURCES` and `STUDIO_DATA`). These variables must be exported explicitly; the application does not automatically load a `.env` file. No credentials were extracted or added, and no API key is required for the offline pipeline.

## Initial scan and provenance

The initial scan found no remaining private host/account/path references in the copied files and no identified credentials. Generic credential patterns matched source-code identifiers; an access-key-shaped sequence occurred inside an upstream embedded WebAssembly Base64 payload. That file matches its pinned selected-file SHA-256. These are classified as false positives, with no matched values recorded here.

All eight selected upstream code/data files matched `vendor/sources.lock.json` after the copy. Original third-party license and notice files remain in `vendor/`; original third-party public attribution and contact details are preserved.

The selected VoiceStudio sentence splitter identifies its Patter origin and MIT license in its header; the overall VoiceStudio repository is AGPL-3.0-only. An intermediate packaging stage verified the Patter MIT notice and identified that the chunker was not called by the current video-rendering path. Final packaging removed that unused helper, its dead calling function and the associated notices from the publication. VoiceStudio remains a research-only source with no distributed code or model weights; seven selected upstream code/data files remain. See THIRD_PARTY.md for the final scope.

## Packaging follow-up

The application relies on two separately pinned runtime checkouts (Archify and PPT Master), Linux native tools, browser rendering, and fonts. The public bootstrap and documentation must describe and verify these requirements. Historical private deployment tests are not proof of a fresh public installation.

Git initialization, the initial public commit, and publication are handled after packaging and independent sanitization. This report documents the initial fork stage; later packaging changes are visible in the public Git commit.

The independent final publication review is recorded in SANITIZATION_REPORT.md.
