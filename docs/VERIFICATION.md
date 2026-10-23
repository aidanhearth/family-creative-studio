# Public release verification

Date: 2026-10-23. These results come from a separate clean project environment with freshly installed locked Python/npm dependencies and freshly downloaded pinned runtime checkouts. They are not copied private-workbench logs. Machine-readable, synthetic-data-only results: [verification.json](verification.json).

## Completed checks

- `./setup.sh`: completed on Linux x86_64 / Python 3.11; doctor passed the browser, CJK font, pinned sources, bundles and actual Bubblewrap namespace checks.
- Python suite: **49 passed**, including revision conflicts, containment, cache integrity, media constraints, relative environment propagation and browser launch-alias preservation.
- JavaScript suite: **4 passed**, including recovery after failed undo and serialized undo.
- `scripts/check_mcp.py`: **14 real stdio tools** discovered; schema, recipes, project creation, patch, comparison and preflight succeeded. An intentional stale revision produced the expected tool error.
- All five render targets succeeded from [assembly.json](../examples/assembly.json): **45 artifacts**, every recorded SHA-256 matched the resulting bytes.
- Video: **6 seconds, 1280×720, 24 fps**. Orbit and explode each contain 72 frames, at least 90% consecutive frames differ, and returning to the first timestamp reproduces its hash on this renderer.
- CAD: STEP re-imported as three valid solids; geometry bounds and analytic volume matched within the recorded tolerance. GLB container, bounds and mesh-volume checks passed.
- PPTX: two slides, 22 editable shapes/text frames, two pictures and two native paths. This checks structure, not complete PowerPoint feature compatibility or artistic quality.
- The README preview was visually inspected and contains only this public synthetic example. Private screenshots, media, jobs, logs and deployment configuration are excluded.
- Independent Python portability review and public-file sanitization were completed; see [SANITIZATION_REPORT.md](../SANITIZATION_REPORT.md) for exact scope.

## Reproduce

Install prerequisites, run `./setup.sh`, then:

```bash
.venv/bin/python -m pytest -q
npm test
.venv/bin/python scripts/check_mcp.py
.venv/bin/family-studio save examples/assembly.json
.venv/bin/family-studio render public-assembly --wait
```

Use a new `STUDIO_DATA` directory if `public-assembly` already exists. Read `status` and check the returned `output_dir`; queued/running is not success. A stale-revision tool error in the MCP smoke check is intentional.

## Limits of this evidence

Only one Linux environment was exercised. This is not a clean Windows/macOS installation result or a promise that Ubuntu's security configuration permits namespaces on every host. The native CAD, browser and FFmpeg dependencies remain prerequisites.

The example is a small synthetic assembly with silent audio, not a representative professional production. It does not test neural speech, image-to-3D, real WebGPU effects, 4K/HDR preservation, long-form production, complete accessibility, new-user usability or artist-level quality. Same-host deterministic screenshots do not establish cross-host bit-for-bit results. No comparative scores against the twelve original applications were measured. See [COMPARISON.md](COMPARISON.md) for deficits and a proposed evaluation plan.
