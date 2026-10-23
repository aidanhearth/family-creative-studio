# Agent quickstart

The CLI and MCP tools operate on the same local store as the browser editor. No model API key is required by the renderer. Your coding assistant supplies the reasoning and authored manifest; the workbench validates and renders it.

Run commands from the project checkout after `./setup.sh` succeeds. See [AGENTS.md](../AGENTS.md) for architecture and [COMPARISON.md](COMPARISON.md) for missing functionality.

## Create and inspect

```bash
.venv/bin/family-studio doctor
.venv/bin/family-studio recipes
.venv/bin/family-studio create assembly_story demo-assembly
.venv/bin/family-studio get demo-assembly
.venv/bin/family-studio schema
```

Recipe IDs are `product_explainer`, `assembly_story` and `media_story`. Each creates a new project; an existing ID is not overwritten. `media_story` supplies a structure, not bundled video or image assets.

The manifest currently permits at most 16 box/cylinder solids and 8 chapters. Dimensions, through-holes, referenced IDs, narration and total requested duration are validated; consult the schema rather than assuming arbitrary CAD or timeline features exist.

## Change by stable ID

Read the revision returned by `get`. For a newly created, otherwise unmodified project it is `1`:

```bash
cat > patch.json <<'JSON'
[
  {"op":"set","target":"solid","id":"tray","values":{"bore":18}},
  {"op":"set","target":"project","values":{"title":"Assembly study"}}
]
JSON
.venv/bin/family-studio patch demo-assembly patch.json --revision 1 --dry-run
.venv/bin/family-studio patch demo-assembly patch.json --revision 1
.venv/bin/family-studio compare demo-assembly 1 --after 2
```

For an existing project substitute its actual current revision. Dry-run returns a diff without saving. A conflict means another edit has been saved: read the current document and reconcile the intended change. Do not keep retrying an old revision or replace another editor's work.

Patch operations are `set`, `add`, `remove` and `move`, with targets `project`, `brand`, `solid` or `beat`. Project/brand support `set` only. Existing objects are addressed by `id`; an addition supplies the new ID inside `values`. A move supplies a zero-based `index`. A whole patch is validated before it is saved.

Dimension references such as `{{tray.bore}}` keep text linked to a part. Removing a part freezes its existing dimension references to their current values and removes focus references; the remaining scene must still satisfy the schema.

## Render and check

```bash
.venv/bin/family-studio preflight demo-assembly
.venv/bin/family-studio render demo-assembly --targets web diagram cad slides video --wait
```

A successful response includes `output_dir`; inspect the actual requested files. A queued or running job is not a completed render. `--wait` times out after 900 seconds by default without canceling the job. Use `--timeout` to change the wait limit, or use `status` with the returned job ID. `cancel` and `retry` also take a job ID, not a project ID. `--force` bypasses the completed-job shortcut; stage cache reuse still depends on stage inputs and verified artifacts.

Only claim quality you have checked. PPTX preserves supported text/shape elements, while 3D and media scenes are represented by still images. Video is 720p at 24 fps. No automatic image generation, ASR, voice cloning or artist-level quality evaluation is supplied.

## Import your own media

```bash
.venv/bin/family-studio media /absolute/path/to/clip.mp4
.venv/bin/family-studio audio /absolute/path/to/narration.wav
```

These commands require real local files and return content-addressed asset identifiers. Copy the returned identifier into the appropriate manifest field: chapter `visual.asset` for PNG/JPEG/MP4, or project `narration_asset` for WAV. Use `visual.mode` `image` or `clip`; clip `start` is a source trim offset, and the chapter duration specifies its requested span. `visual.audio` accepts `voice`, `source` or `silent`; source audio requires a clip, and it cannot be combined with an imported project narration track. Always run `preflight` after changing media or trim ranges.

Media is normalized before use, so this is not a lossless archival editor. Imports and renders have size, duration and resolution limits. User media stays in `STUDIO_DATA`; it must not be committed to the repository by default.

## MCP stdio

Configure your client's stdio server with an **absolute** command pointing at this checkout's `.venv/bin/family-studio`, arguments `["mcp"]`, and the checkout as its working directory. The following illustrates the common `mcpServers` layout; replace the paths and adapt the wrapper keys to your client:

```json
{
  "mcpServers": {
    "family-creative-studio": {
      "command": "/absolute/path/to/family-creative-studio/.venv/bin/family-studio",
      "args": ["mcp"],
      "cwd": "/absolute/path/to/family-creative-studio",
      "env": {
        "STUDIO_DATA": "/absolute/path/to/creative-studio-data"
      }
    }
  }
}
```

`STUDIO_DATA` is optional. Omit it to share the checkout's default `.state` with its browser UI and CLI, or use the same explicit directory everywhere. Clients that do not support `cwd` can use a launcher that changes to the checkout first. The stdio process is an MCP server, not an interactive prompt.

Fourteen tools are exposed:

| Purpose | Tools |
|---|---|
| Discover | `studio_capabilities`, `studio_schema`, `studio_recipes` |
| Read/create | `studio_projects`, `studio_get`, `studio_create` |
| Edit/compare | `studio_save`, `studio_patch`, `studio_compare` |
| Validate/render | `studio_preflight`, `studio_render`, `studio_status` |
| Manage jobs | `studio_cancel`, `studio_retry` |

Use capabilities → get/create → patch dry-run → patch → preflight → render → status. `studio_render` queues work and returns a job ID; poll `studio_status` at reasonable intervals until it succeeds or fails. Importing local media currently uses the CLI or browser, not an MCP upload tool. Client configuration and authentication to the coding assistant itself are outside this renderer.
