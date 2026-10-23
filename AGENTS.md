# Family Creative Studio

**Version:** 0.3.0 | **Port:** 8765 (loopback only) | **Stack:** Python 3.11, FastAPI, SQLite, Three.js, FFmpeg, OpenCASCADE

## What
A local manifest-driven workbench for web, vectors, CAD, editable presentations and video. Twelve upstreams were researched; selected mechanisms/data from eleven are used. Read `docs/COMPARISON.md` before claiming parity or quality advantages.

## Quick Start

Install the Linux prerequisites in README.md, then:

```bash
./setup.sh
.venv/bin/family-studio serve
.venv/bin/python -m pytest -q
```

Open http://127.0.0.1:8765/. The renderer targets Ubuntu 24.04/Linux x86_64 with usable Bubblewrap namespaces and Chrome/Chromium. A Mac can control it through a loopback SSH tunnel; native macOS/Windows rendering is unsupported. See the agent guide.

## Commands

```bash
./setup.sh                                          # Locked dependencies, browser build, two pinned upstreams
npm run build                                       # Browser bundle
npm test                                            # JavaScript tests
.venv/bin/python -m pytest -q                        # Python tests
.venv/bin/family-studio doctor                       # Availability and limits
.venv/bin/family-studio schema                       # Current manifest JSON schema
.venv/bin/family-studio recipes                      # Recipe IDs
.venv/bin/family-studio create assembly_story sample  # New ID required
.venv/bin/family-studio get sample                   # Current manifest and revision
.venv/bin/family-studio assets                       # Imported original asset metadata
.venv/bin/family-studio timeline sample              # Editable timeline interchange
.venv/bin/family-studio preflight sample             # Asset, trim and contrast checks
.venv/bin/family-studio render sample --targets diagram cad slides --wait
.venv/bin/family-studio mcp                          # 19 tools over stdio
.venv/bin/python scripts/bootstrap_sources.py --all  # Optional research checkouts, no models/LFS
```

No standalone lint, coverage or Docker workflow is configured.

## Architecture

```text
studio/       Schemas, revision store, APIs, CAD/media workers, exports and MCP
web/          Editor, scene viewer and effects
scripts/      Build, source bootstrap and geometry/scene inspection
vendor/       Selected upstream files, licenses and source hashes
examples/     Public example inputs
tests/        Python, JavaScript and browser checks
docs/         Agent guide, comparisons, verification and security boundaries
```

CLI, HTTP and MCP share `Store`; validated edits use revision checks. Workers render immutable snapshots, verify artifact hashes and reuse verified stage caches. CAD solids and an imported visual GLB are independent sources; never describe the GLB as converted to STEP. Draft CAD previews use the same kernel and verify their input/output hashes.

## Key Files

- `studio/schema.py`: geometry, scene, timeline and output settings.
- `studio/operations.py`: stable-ID atomic edits and semantic differences.
- `studio/geometry_kernel.py`: direct build123d/OpenCASCADE construction.
- `studio/geometry_preview.py`: unsaved exact CAD previews and cache receipts.
- `studio/media_assets.py`: preserved original imports and preflight checks.
- `studio/timeline.py`: revision- and source-hash-protected timeline exchange.
- `studio/pipeline.py`: cross-format export and verification.
- `studio/ppt_worker.py`: structured native slides and embedded media.
- `studio/mcp_server.py`: stdio interface.
- `vendor/sources.lock.json`: pinned sources and vendored hashes.

## Configuration

Optional environment variables; `.env.example` is not loaded automatically.

| Variable | Required | Description |
|---|---|---|
| `STUDIO_DATA` | No | State/assets/cache; defaults to project `.state` |
| `STUDIO_SOURCES` | No | Pinned checkouts; defaults to project `.sources` |
| `STUDIO_BROWSER` | No | Explicit Chrome/Chromium executable |
| `PYTHON_BIN` | No | Python 3.11 for setup when `uv` is unavailable |

## Working Rules

Read revisions before editing; preview patches, then submit the same expected revision. Up to 2,048 operations form one atomic edit; CLI/HTTP JSON is bounded to 16 MiB. Discover limits through the schema rather than treating maxima as performance guarantees. Check preflight and actual job results. Preserve originals, licenses and source hashes; exclude user state, media and private machine details from Git. Do not claim ASR, image generation, voice cloning, GLB-to-CAD conversion or all-upstream superiority. Read `docs/SECURITY.md` before changing execution boundaries.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/AGENT-QUICKSTART.md](docs/AGENT-QUICKSTART.md).
