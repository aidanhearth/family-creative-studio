# 0.3.0 verification

Date: 2026-10-23 UTC. These checks use synthetic local inputs and the pinned Linux renderer. Machine-readable results: [verification.json](verification.json). The prior release's separate installation and sample results remain in [verification-0.2.0.json](verification-0.2.0.json).

## Completed checks

- **151 Python checks passed in 81.03 seconds**, including all selected native media, PPT, multi-format and browser integrations; no selected test was skipped.
- **18 JavaScript tests passed** in native Node child processes, covering raw dimension expressions, draft edits, animation selection, semantic saves, geometry bounds, audit findings and serialized undo. Frontend build passed.
- **19 actual stdio MCP tools** were discovered. Creation, patch, comparison, timeline, assets and preflight succeeded; a stale revision was rejected as intended.
- **Four end-to-end render cases passed**, with every artifact hash checked: CAD/WAV/motion (62), original GLB/custom SVG (53), actual 4K60 source (33), and portrait source plus native PPT (64). All report one H.264 composition generation, with import/concatenation/final video mux avoiding additional picture encodes.
- The CAD story exports two valid STEP solids with volume **2720.774288665791 mm³**, agreeing with the constructed geometry within **1.3×10⁻¹¹ mm³**. STL/GLB mesh tolerance and bounds checks passed. Separate geometry tests cover all seven sources, rotation, bores, fillets/chamfers, multiple-solid STEP and Boolean operations.
- The CAD PPTX contains **2 slides, 447 editable shapes, 429 native paths, 1 embedded movie and 2 narration tracks**. The custom-SVG case contains **2 slides, 12 editable shapes, 1 native path, 1 movie and no narration tracks**, with automatic 250 ms slide timing. Counts include individual tessellated geometry shapes; they do not measure editing convenience. Final OOXML animation references were validated after movies were added. Translated imported canvas rectangles remain editable at their original position instead of becoming incorrect solid backgrounds.
- Imported SVG viewBox fitting, inherited text color/font size, uniform scaling and rotation were verified as native editable output. Unsupported text shear, reflection and nonuniform scaling produce an explicit conversion error, rather than silently rasterizing the artwork.
- Actual browser checks cover three editor journeys plus skinned bounds, extreme scale animation and selection of the second GLB animation. GLB source bytes remain unchanged; the selected animation persists after save/reopen. Frame reset and camera coverage are checked independently of an arbitrary minimum moving-pixel percentage.
- Bounded FFmpeg checks cover source audio/narration mixing, gain/fades, source frame-rate handling, HDR-to-SDR conversion, full-frame text overlays and presentation movie audio settings. The 4K60 integration is **six frames / 0.1 seconds**, sufficient to catch forced resolution/rate reduction, not to establish long-form performance.

The portrait case preserves **360×640 / 30 fps** across full, editorial and split layouts, plus an imported SVG. Decoded frames verify top/bottom text placement, paper-colored margins, poster/media alignment and an undistorted circle; the corresponding native PPT remains 16:9. Odd-sized media rectangles compose in RGBA before a single explicit BT.709 conversion. The Mac project MCP launcher also returned all 19 tools through its existing SSH route.

## Separate GPU viewer checks

On **Apple M5 / Chrome 155**, the viewer rendered seven CAD parts using `ANGLE Metal Renderer: Apple M5`; focus and repeat-frame checks passed, with nonuniform pixels and no lost context. The final 0.3.0 viewer was rebuilt on the Mac, and its SSH-connected editor loaded the shared project. WebGPU returned a non-fallback Apple Metal adapter. This validates the browser viewer on a Mac, not native macOS CAD/FFmpeg workers or every shader effect.

On an **NVIDIA Blackwell / Chrome 151** host, the Vulkan route displayed the same seven parts and returned a non-fallback NVIDIA WebGPU adapter. WebGL vendor/renderer strings were empty and transient command-buffer errors were recorded, so WebGL hardware identity remains unverified. The default browser backend failed to initialize the viewer. This earlier working-tree check is recorded as a compatibility limitation, not a blanket GPU pass.

Both checks used fresh headless browser profiles and synthetic assets. No human desktop, login profile or paid model API was used for rendering. Same-renderer repeatability does not establish cross-GPU pixel identity.

## Reproduce

Install prerequisites and run `./setup.sh`, then:

```bash
npm run build
npm test
STUDIO_MEDIA_INTEGRATION=1 STUDIO_PPT_INTEGRATION=1 \
STUDIO_PIPELINE_INTEGRATION=1 STUDIO_BROWSER_TESTS=1 \
  .venv/bin/python -m pytest -q
.venv/bin/python scripts/check_mcp.py
```

These four flags select actual synthetic FFmpeg, PPT, multi-format pipeline and headless browser tests; they are not application configuration. Without them, the corresponding tests are explicitly skipped. Bubblewrap namespaces and browser subprocesses must be available. Keep the renderer's sandbox enabled. A stale-revision error from the MCP smoke check is intentional.

For an interactive sample:

```bash
.venv/bin/family-studio create assembly_story example-assembly
.venv/bin/family-studio preflight example-assembly
.venv/bin/family-studio render example-assembly --wait
```

Use a new project ID or a new `STUDIO_DATA` directory when repeating a sample. Queued/running is not completion; inspect the job and its `output_dir`.

## Evidence limits

PPTX structure, embedded media and animation references are verified; desktop PowerPoint, Keynote and LibreOffice playback remain separate acceptance tasks. Outputs use SDR BT.709; preserved HDR source bytes do not imply HDR mastering. Schema/import size limits are not throughput guarantees. No full Windows/macOS render installation, neural voice quality, image generation, image-to-3D accuracy, exhaustive accessibility, first-time-user study or head-to-head artistic quality comparison was performed.

Native model source reviews informed fixes but are not executable test results or proof of superiority. See [COMPARISON.md](COMPARISON.md) for retained gaps, and [SANITIZATION_REPORT.md](../SANITIZATION_REPORT.md) for the public source review.
