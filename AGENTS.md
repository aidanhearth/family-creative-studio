# Family Creative Studio

**Version:** 0.2.0 | **Port:** 8765 (loopback only) | **Stack:** Python 3.11, FastAPI, SQLite, Three.js, FFmpeg, OpenCASCADE

## What
A local manifest-driven workbench producing web, SVG, CAD, editable PPTX elements and short videos. It integrates selected upstream mechanisms, not twelve complete applications; read `docs/COMPARISON.md` before describing capability.

## Quick Start

Install Linux prerequisites from README.md, then:

```bash
./setup.sh
.venv/bin/family-studio serve
.venv/bin/python -m pytest -q
```

Open http://127.0.0.1:8765/. Target Ubuntu 24.04/Linux x86_64; rendering requires usable Bubblewrap namespaces and Chrome/Chromium. Native macOS/Windows rendering is unsupported.

## Commands

```bash
./setup.sh                                          # Install locked dependencies, build, fetch two pinned sources
npm run build                                       # Bundle browser code
npm test                                            # JavaScript tests
.venv/bin/python -m pytest -q                        # Python tests
.venv/bin/family-studio doctor                       # Availability and limitations
.venv/bin/family-studio schema                       # Manifest JSON schema
.venv/bin/family-studio recipes                      # Discover recipe IDs
.venv/bin/family-studio create assembly_story sample  # New project; ID must not exist
.venv/bin/family-studio get sample                   # Read manifest and current revision
.venv/bin/family-studio preflight sample             # Check required scene assets
.venv/bin/family-studio render sample --targets diagram cad slides --wait
.venv/bin/family-studio mcp                          # MCP stdio server
.venv/bin/python scripts/bootstrap_sources.py --all  # Optional research sources, no models/LFS
```

No standalone lint, coverage or Docker workflow is configured.

## Architecture

```text
studio/       Schema, revision store, APIs, worker, render stages and MCP
web/          Browser editor, viewer and interface copy
scripts/      Browser build, pinned source bootstrap and geometry helpers
vendor/       Selected upstream files, licenses and source hash manifest
examples/     Public example data
tests/        Python and JavaScript checks
docs/         Agent guide, comparison and security boundaries
```

CLI, HTTP and MCP share `Store`; edits validate a Manifest and compare revisions. A worker renders immutable snapshots, verifies artifacts and reuses matching stage caches. `.state`, `.sources`, `.venv` and generated `dist` are local and excluded from Git.

## Key Files

- `studio/schema.py`: bounded document and cross-reference validation.
- `studio/operations.py`: stable-ID atomic edits and semantic differences.
- `studio/store.py`: revisions, jobs and artifact bookkeeping.
- `studio/pipeline.py`: export orchestration.
- `studio/server.py`: local HTTP application.
- `studio/mcp_server.py`: stdio tools for agents.
- `studio/diagnostics.py`: environment checks and capability limits.
- `vendor/sources.lock.json`: pinned upstream commits and file hashes.
- `setup.sh`: first-time bootstrap and readiness check.

## Configuration

Environment variables are optional; `.env.example` is documentation, not automatically loaded.

| Variable | Required | Description |
|---|---|---|
| `STUDIO_DATA` | No | State directory; defaults to project `.state` |
| `STUDIO_SOURCES` | No | Pinned checkouts; defaults to project `.sources` |
| `STUDIO_BROWSER` | No | Explicit Chrome/Chromium executable |
| `PYTHON_BIN` | No | Python 3.11 executable when setup cannot use `uv` |

## Working Rules

Read the current revision before updating. Preview patches with `--dry-run`, then submit with that revision; a conflict requires rereading, not overwriting. Use `preflight` before rendering; report actual job status and artifact paths. Never claim image generation, voice cloning or arbitrary image-to-3D is implemented. Keep user media, state, credentials and machine-specific paths out of commits; retain upstream notices and hashes. See `docs/SECURITY.md` for sandbox limits.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/AGENT-QUICKSTART.md](docs/AGENT-QUICKSTART.md).
