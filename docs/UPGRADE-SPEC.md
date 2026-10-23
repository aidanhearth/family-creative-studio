# Creative Studio capability restoration

Baseline: `5fa508fb6ff0afee113f65c24b54d6c98eebd39b`. The requested outcome is a genuinely more capable, easier creative workbench. Address the complete independent Fable and Argon code reviews, without treating file inclusion or a larger tool list as functional integration.

## Acceptance workstreams

1. Editing: preserve dimension expressions during ordinary editing; separate expression input from live preview; expose subtitle, focus, per-part color, ordering, geometry and output controls; structural edits stay local until Save; meaningful audit findings; consistent focus and effects across preview/export.
2. Media: preserve original uploads and alpha/color information; never silently force source video to 720p/24fps; configurable source/720p/1080p/2160p and source/24/25/30/50/60 fps; one lossy video generation for source clips; subtitles in that generation; stream-copy final video; two-pass loudness and cut fades; voice/source mixing; import/export editable timelines; authored caption timing with honest provenance (automatic ASR and word alignment remain separate engines).
3. Geometry: more than box/cylinder. Add rotations, sphere/cone/torus, polygon extrusion, fillet/chamfer, validated boolean combinations and actual CAD import/program extension where feasible. STEP/GLB/STL, bounds and volume checks must measure the resulting geometry rather than obsolete primitive formulas. Preserve part identity and focus through exports. Complex geometry must render honestly, not silently display a box approximation.
4. Slides and diagrams: multiple layouts; editable vector diagrams; embedded media and narration with timing; access to the upstream diagram renderer's actual graph schema/types rather than only linear chapter graphs. Use original SVG vector conversion with bounded imports; full source-document/template/PPTX round-trip authoring remains an upstream workflow.
5. Agent and creative workflows: MCP/CLI/HTTP asset import and inspection, timeline operations and revisions; concrete integration seams for original specialized engines/skills. State required external providers/models explicitly. Do not claim voice cloning or generative image/3D output from merely adding a configuration field.
6. Reliability: early contrast/asset/geometry checks; remove unused scoring claims; complete provenance/cache dependencies; no misleading copy; regression and real artifact checks for changed functionality; independent standards and specification review.
7. Delivery: update README, agent instructions and comparison per upstream; record actual verified improvements and remaining external dependencies; public-safe commit and push.

## Shared implementation contract

Keep existing manifests readable with defaulted additive fields. `schema_version` stays 1 for this backwards-compatible extension.

- `Manifest.video`: `{resolution: 'source'|'720p'|'1080p'|'2160p', fps: 'source'|24|25|30|50|60, crf: 0..28, captions: bool, normalize_audio: bool}`; default source/source/18/true/true.
- `Manifest.slides`: `{layout: 'editorial'|'full'|'split', narration: bool, autoplay: bool, transition: 'fade'|'none', animation: 'none'|'fade'}`; defaults editorial/true/true/fade/none. Per-beat `layout` can override.
- `Visual.audio`: voice/source/silent/mix. `voice_gain` default 1 and `source_gain` default 1 (finite 0..2). Per-beat `narration_asset` optionally overrides the global WAV. Imported global narration may coexist with source-only chapters; timeline offsets remain authored offsets.
- `Solid`: preserve existing fields; add `rotation` degrees triple, `fillet`, `chamfer`, shape-specific parameters. Geometry owner documents the completed fields before UI completion.
- Raise arbitrary tiny authoring limits while maintaining finite resource bounds: up to 256 solids and 256 beats, 0.1..600 seconds/beat and 7200 seconds total, 16 KiB narration/beat. Render jobs retain cancellation, timeouts and log caps.
- The media worker resolves actual output width/height/fps from source metadata and `Manifest.video`; record them in `edit.edl.json`. Pipeline verification reads that contract rather than hard-coded 720p/24.
- Scene worker applies focus after `viewer.ready`, uses configured output geometry, and stores that input in the cache identity. Viewer exposes actual CAD rather than pretending unsupported shapes are boxes.

## Coordination

One writer per file. Media owner: `studio/video.py`, `studio/media_assets.py`, `studio/assets.py`, `studio/media_worker.py`, media-specific new helper/tests. Geometry owner: `studio/schema.py`, `studio/cad_worker.py`, `scripts/anatomy.mjs`, `scripts/glb-check.mjs`, geometry-specific new helpers/tests. Frontend owner: `web/app.js`, `web/state.mjs`, `web/index.html`, `web/app.css`, `web/viewer.js`, `web/shader.js`, browser-specific tests. Coordinator owns pipeline, scene worker, PPT, APIs/MCP/CLI, operations, store, graph/engine adapters, integration tests and documentation. No worker commits/pushes or edits another owner's files.
