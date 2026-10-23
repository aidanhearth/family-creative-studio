# Agent quickstart — 0.3.0

CLI, HTTP and the 19 MCP tools operate on the same local store. The renderer requires no model API key: your coding assistant authors the manifest, and the workbench validates and renders it. Run commands from the checkout after `./setup.sh` succeeds. See [AGENTS.md](../AGENTS.md), [implementation comparison](COMPARISON.md), and [verification scope](VERIFICATION.md).

## Create and inspect

```bash
.venv/bin/family-studio doctor
.venv/bin/family-studio recipes
.venv/bin/family-studio create assembly_story demo-assembly
.venv/bin/family-studio get demo-assembly
.venv/bin/family-studio schema
```

Recipe IDs are `product_explainer`, `assembly_story` and `media_story`. Creating an existing ID fails; recipes do not include commercial media or model weights.

| Document limit | Current contract |
|---|---|
| CAD parts / chapters | Up to 256 of each; at least one chapter |
| Chapter / project duration | 0.1–600 seconds per chapter; total authored duration at most 7,200 seconds; the audio path also rejects an adjusted timeline over 7,200 seconds |
| Narration | At most 16 KiB of UTF-8 text per chapter |
| Title / body | Chapter title 28 characters; body 85 characters |
| Atomic patch | 1–2,048 operations; CLI/HTTP manifest, patch and timeline JSON at most 16 MiB |
| Custom diagram | JSON at most 256 KiB, nesting at most 20 levels |

These are validation limits, not evidence that every maximum-size document renders quickly or within available memory. Dimensions remain positive and at most 1,000 mm per axis; placement is bounded to ±2,000 mm. Query the current schema for all constraints.

## Edit by stable ID

Read the revision returned by `get`. A newly created, otherwise unchanged project has revision `1`:

```bash
cat > patch.json <<'JSON'
[
  {"op":"set","target":"solid","id":"tray","values":{"bore":18}},
  {"op":"set","target":"project","values":{"title":"Assembly study","video":{"resolution":"1080p","fps":30},"slides":{"layout":"split","narration":true}}}
]
JSON
.venv/bin/family-studio patch demo-assembly patch.json --revision 1 --dry-run
.venv/bin/family-studio patch demo-assembly patch.json --revision 1
.venv/bin/family-studio compare demo-assembly 1 --after 2
```

For an existing project, substitute its current revision. Dry-run returns changes without saving; a conflict requires rereading and reconciling the document. `set`, `add`, `remove` and `move` address `solid`/`beat` objects by stable ID. Project and brand allow `set` only. Additions supply `values.id`; moves supply a zero-based `index`. Setting a nested object such as `video`, `slides` or `visual` replaces that object, so send its intended complete settings; omitted members take schema defaults.

Tokens such as `{{tray.bore}}` keep text linked to part dimensions. Removing a part freezes its text references to current values and removes its chapter focus references; remaining boolean references and scenes must still validate.

## Import original assets

Replace the example paths with your own files:

```bash
.venv/bin/family-studio media /absolute/path/to/clip.mp4
.venv/bin/family-studio audio /absolute/path/to/narration.wav
.venv/bin/family-studio cad /absolute/path/to/part.step
.venv/bin/family-studio scene /absolute/path/to/scene.glb
.venv/bin/family-studio svg /absolute/path/to/slide.svg
.venv/bin/family-studio assets
```

Each command inspects and stores the original bytes under a SHA-256 asset ID. Imports no longer replace the original with a resized or transcoded copy. Derived posters, video and slide media are separate outputs. MOV-family containers are inspected through the MP4/MOV demuxer and stored with the internal `.mp4` asset suffix; the suffix does not mean the original bytes were converted.

| Asset | CLI/HTTP limit and use |
|---|---|
| PNG/JPEG | 512 MiB; one frame, at most 64 megapixels; assign `beat.visual.asset`, mode `image` |
| MP4/MOV | 512 MiB; 0.1–7,200 seconds, at most 8,192 pixels per side/64 megapixels/120 fps; one picture track; assign `beat.visual.asset`, mode `clip` |
| PCM WAV | 512 MiB; 0.1–7,200 seconds, mono/stereo, 8–192 kHz, 8/16/24/32-bit PCM; assign project or chapter `narration_asset` |
| STEP | 50 MiB; valid solid geometry; assign `solid.asset` with kind `step` and the inspected `size_mm` dimensions |
| GLB | 50 MiB; self-contained glTF 2.0; assign project `scene_asset` |
| Native SVG | 2 MiB/50,000 elements; assign `beat.svg_asset` with visual mode `diagram` |

MCP `studio_import_asset` accepts the same kinds (`media`, `audio`, `cad`, `scene`, `svg`), but decoded inline bytes are limited to 8 MiB and each format's smaller limit still applies. Use CLI/HTTP for larger inputs. SVG supports bounded native vectors/text and local fragment references; scripts, external URLs, embedded raster images and unsupported elements are rejected. GLB external resources, Draco, Meshopt, BasisU and unsupported required extensions are rejected; re-export a self-contained uncompressed asset. Original materials, textures, hierarchy and animations remain in the stored GLB.

## CAD and visual scenes are independent

CAD kinds are `box`, `cylinder`, `sphere`, `cone`, `torus`, `extrusion` and `step`. Operations run directly through build123d/OpenCASCADE rather than a generated-code broker. Each part supports XYZ rotation, placement, a local through-hole, and either all-edge fillet or all-edge chamfer. Extrusions use a validated simple polygon in normalized coordinates. Boolean `union`, `subtract` and `intersect` tools must refer to preceding parts in document order; set `construction: true` to keep a tool out of deliverables. Impossible or empty operations fail instead of silently substituting a primitive.

Imported STEP geometry is centered without scaling; its declared `size` must match inspected bounds. The exported STEP is reopened and checked against the actual post-operation shape; STL and CAD GLB are checked against its bounds/volume. These checks do not establish manufacturability or constraint-solving capability.

`studio_preview_geometry(manifest)` builds the draft using the same CAD worker without saving a revision. It returns `saved: false`, an HTTP-relative preview URL, a `key`, geometry and validation data. STEP inputs and all five cached CAD preview outputs are hash-checked before reuse; a missing or changed output causes a rebuild. The URL belongs to the running HTTP service using the same state directory; an MCP-only process does not itself serve HTTP.

When `scene_asset` is set, the web viewer and orbit/explode chapters use the imported GLB. CAD exports and CAD diagram chapters still use `manifest.solids`. `geometry-sources.json` records this distinction. Importing GLB does **not** generate engineering STEP/STL, and its materials are not applied to the separate CAD assembly. Imported scenes use their complete hierarchy rather than CAD part focus. Set `scene_animation` to the zero-based clip index (default 0), or choose a named clip in the editor. One selected clip is evaluated within camera presets; concurrent clip blending and a general animation editor remain separate work.

## Timeline, audio and output settings

```bash
.venv/bin/family-studio timeline demo-assembly > timeline.json
.venv/bin/family-studio timeline-import demo-assembly timeline.json --revision 2 --dry-run
```

Edit exported `timeline.segments`, `video` or `slides`, then import with the revision from the current project. The exported `source_sha256` must still match the source manifest; re-export after unrelated edits. Timeline import preserves stable chapter IDs, dimension expressions, trims, narration assets, mixing and layouts. A dry-run checks assets and reports changes without saving. `edit.edl.json` in a render records actual audio-adjusted timing, while the interchange document contains authored timing.

For clips, `visual.start` is the source offset and chapter `duration` is the requested span. `visual.audio` accepts `voice`, `source`, `silent` or `mix`; `source` and `mix` require a source audio track. `mix` combines narration and source with independent `voice_gain`/`source_gain` (0–2). A chapter WAV overrides the project WAV and starts at zero; a project WAV uses authored timeline offsets. Without imported narration, `voice`/`mix` use eSpeak NG draft speech. There are short cut fades, a limiter, and optional output loudness normalization; no ASR, word-aligned subtitles, automatic ducking or arbitrary multitrack mixer is provided.

`video.resolution` accepts `source`, `720p`, `1080p`, `2160p`; `video.fps` accepts `source`, 24, 25, 30, 50, 60. `source` selects the largest referenced image/video display canvas and the highest referenced clip frame rate, preserving its rational value. With no such media it defaults to 1920×1080 and 30 fps. The output is a single constant-frame-rate canvas, not each clip's native variable timing. `crf` ranges from 0 to 28; `captions` and `normalize_audio` are switches. Original HDR remains stored, but composed video is SDR BT.709 with HDR tone mapping, H.264 picture and 48 kHz stereo audio.

Layouts are `editorial`, `full` and `split`, selectable globally through `slides.layout` and overridden by a chapter's `layout`. PPTX uses structured masters/layouts, supported native editable SVG/text, notes, optional narration, fade/none transitions and fade/none shape animation. Clip and 3D motion chapters embed MP4 playback; they are not native editable 3D objects. `slides.narration` controls separate audio tracks, and `slides.autoplay` controls timings. With narration disabled, source/mix chapters retain their source component while voice/silent chapters do not silently substitute source audio. Playback behavior still depends on the presentation application.

## Diagrams and browser effects

Set `manifest.diagram` to `{ "kind": "…", "document": { … } }` for a custom Archify input. Supported kinds: `architecture`, `workflow`, `sequence`, `dataflow`, `lifecycle`, `erd`, `tree`, `class`, `timeline`, `waterfall`, `explainer`. Use the pinned Archify schemas/examples for the chosen kind; the wrapper does not invent missing graph structure. Diagram output remains named `workflow.html` and its input `workflow.json` regardless of kind. Without a custom document it derives a workflow from chapters. No repository analysis or source-code mapping is performed automatically.

`effect` exposes Circle/LinearGradient settings, opacity and enablement in the editor and published viewer. WebGPU capability and the CSS fallback are explicit; this is not a full shader graph editor and browser effects do not imply the same effect is baked into PPT/video. Brand text colors are checked against paper at 4.5:1 during preflight and rendering; this is a contrast check, not a full accessibility or artistic evaluation.

## Render and inspect

```bash
.venv/bin/family-studio preflight demo-assembly
.venv/bin/family-studio render demo-assembly --targets web diagram cad slides video --wait
```

Success includes `output_dir`; inspect the requested artifacts and their checks. A queued job is not complete. Waiting defaults to 900 seconds, adjustable with `--timeout`; a wait timeout does not cancel the worker. `status`, `cancel` and `retry` take the returned job ID. `--force` bypasses the completed-job shortcut, while verified stage reuse can still occur. A schema maximum or source-resolution setting is not a promise that a two-hour 4K scene will finish within resource budgets. See [VERIFICATION.md](VERIFICATION.md) for actual tested outputs rather than inferring quality from settings.

## MCP stdio

Use an absolute executable path, arguments `["mcp"]`, and the checkout as working directory. This common layout is illustrative; adapt its wrapper keys to the client's version:

```json
{
  "mcpServers": {
    "family-creative-studio": {
      "command": "/absolute/path/to/family-creative-studio/.venv/bin/family-studio",
      "args": ["mcp"],
      "cwd": "/absolute/path/to/family-creative-studio",
      "env": {"STUDIO_DATA": "/absolute/path/to/creative-studio-data"}
    }
  }
}
```

Omit `STUDIO_DATA` to use the checkout's `.state`, or set the same directory for CLI, HTTP and MCP. Clients without `cwd` can use a launcher that changes directory first. Client authentication is outside the renderer.

| Purpose | Tools |
|---|---|
| Discover | `studio_capabilities`, `studio_schema`, `studio_recipes` |
| Read/create | `studio_projects`, `studio_get`, `studio_create` |
| Edit/compare | `studio_save`, `studio_patch`, `studio_compare` |
| Import/list assets | `studio_import_asset`, `studio_assets` |
| Exchange timeline | `studio_timeline`, `studio_import_timeline` |
| Draft CAD | `studio_preview_geometry` |
| Validate/render | `studio_preflight`, `studio_render`, `studio_status` |
| Manage jobs | `studio_cancel`, `studio_retry` |

Use capabilities → get/create → import/patch dry-run → patch → preflight → render → status. Poll at reasonable intervals and report actual errors rather than claiming completion.

## Mac control with a headless Linux renderer

The Mac can run its coding assistant and browser while rendering stays on a Linux machine. Install the project on Linux, keep it bound to loopback, and start it in a persistent terminal/session there. No remote desktop or Mac screen control is needed. The following placeholders must be replaced with your own existing SSH account and checkout path:

```bash
# Linux renderer, inside its checkout:
.venv/bin/family-studio serve

# Mac terminal, using an existing SSH account:
ssh -N -T -L 18766:127.0.0.1:8765 renderer-user@renderer-host
```

Open `http://127.0.0.1:18766/` on the Mac while the tunnel is active. SSH authentication stays in your existing configuration; no credentials belong in the manifest or repository. For a Mac MCP client, use `ssh` as command and arguments like `["-T", "renderer-user@renderer-host", "cd /absolute/project/path && exec .venv/bin/family-studio mcp"]`, with a quiet non-interactive remote shell. Use shell-quoted paths if they contain spaces. The stdio route and HTTP tunnel are separate connections to the same Linux state; the tunnel does not relocate rendering to the Mac.

For media on the Mac, copy it to a designated Linux input directory and run the corresponding import command there, or pipe bytes to a CLI import using `-` as its file argument. Local files are not automatically visible on the remote host. This architecture does not claim native Mac CAD/FFmpeg support, multi-user access control or a public hosted service.
