# Source review and repair decisions

The 0.3.0 changes address concrete regressions in the initial integration. Two native model consultations compared a working-tree snapshot with baseline `5fa508f` and the pinned upstream code, using source reading only. Executable acceptance was performed separately by the implementation team.

- **Claude Fable 5.1**, max effort: native response metadata independently reported the requested model. Its main conclusion was that most severe integration restrictions had been restored, with narrow improvements, but not superiority over all twelve specialist engines.
- **Gemini 4 Argon**, high effort: the native Antigravity route was configured for this model and returned a report. The adapter did not supply independent actual-model attestation. Its suggestions were individually checked against the code.

Neither report is a quality certification. Raw reports included private deployment context and some stale or unsupported claims; this document records the verified decisions.

| Finding | Decision and implementation | Evidence |
|---|---|---|
| Forced low-resolution, fixed-rate video and repeated picture encoding | Preserve original upload bytes; select source canvas/rate or explicit settings; one composition encode with stream-copy concatenation/mux | Actual 4K60 source integration and media regression tests |
| Restricted geometry and proxy diagrams | Seven geometry sources, imported STEP, rotations, edge features and ordered Booleans; actual post-operation meshes drive diagrams and previews | STEP re-import, independent STL measurement, GLB bounds/volume/part IDs |
| Imported GLB framing used rest-pose bounds | Frame the evaluated pose, including skin deformation and scale changes; interactive explode uses the same framing path | Portrait-viewport skin/scale tests and repeat-frame checks |
| Imported GLB evaluated only the first clip | Select one clip by `scene_animation`; show names/durations, persist selection, reset on source change, reject absent indexes | Actual second-clip channel evaluation and editor save/reopen test |
| PPT narration, movies and native SVG were incomplete | Structured native slide export, narration, movies, timing, editable vectors/text, uniform SVG fit; validate final animation references | Real PPT worker and complete multi-format pipeline tests |
| Imported background extraction ignored transforms | Restrict background promotion to generated slides; retain imported canvas rectangles as editable geometry | Actual translated-rectangle PPT regression |
| SVG fit changed text scale or failed conversion | Resolve inherited metrics before baking similarity transforms; preserve vectors and text | Native OOXML coordinates, font size/color, rotation and path tests |
| Undo/redo and form edits could lose work | Serialize captures/replay and protect clear() from stale asynchronous history; keep raw dimension tokens | JavaScript regression tests plus actual browser journeys |
| Stale capability descriptions | Align doctor, CLI/MCP guide, README and comparison with the implemented contracts | 19-tool stdio check and documented limits |
| Non-16:9 source canvas used incompatible text/media coordinates | Preserve the source aspect ratio and generate film-specific layout; keep native PPT at 16:9 | Portrait composition regression and actual source-canvas rendering |

## Claims not adopted

- Three files absent from the Fable review snapshot were packaging omissions, not deleted repository files. The dependency lock, attribution and fork report are present.
- Source gain defaults to **1** under the accepted contract. Changing it to 0.2 was not a bug fix.
- A global WAV is sliced on authored intervals; it does not fall back to eSpeak between those intervals. The claimed mixed-clock offset defect did not match this code path.
- The dimension register explicitly shows authored CAD parameters. Post-operation bounding boxes and volumes are separately available in geometry/CAD validation outputs. Renaming one as the other would lose useful information.
- Impeccable runs as an editor audit. The rendering gate is the shared contrast check; the audit is not a mandatory pipeline stage.
- Some Gemini references named nonexistent modules or inaccurate counts. They were not used as evidence. The actual prompt catalog contains 19 styles and 22 templates; the actual MCP server exposes 19 tools.

## Remaining differences from specialist applications

Neural voice cloning/transcription, image generation, reference-image reconstruction, complete CAD sketch/constraint/drawing workflows, transcript-aligned editing, a full 3D scene/rig editor and the complete upstream design/diagram/effects toolsets remain specialist workflows. Imported assets connect those workflows to this workbench; an import interface is not the generation engine itself.

The gains demonstrated here are more faithful asset handling, expanded deterministic geometry, coordinated formats and safer revision-based editing. A claim of better artistry, professional-task coverage, speed or ease of use requires matched-input evaluation with people and original tools. See the twelve-project matrix in [COMPARISON.md](COMPARISON.md) and the actual acceptance scope in [VERIFICATION.md](VERIFICATION.md).
