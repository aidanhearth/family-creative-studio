# Contributing

Start with [README.md](README.md) for Linux prerequisites and [AGENTS.md](AGENTS.md) for architecture. Keep the distinction between implemented output, missing capabilities and unmeasured quality explicit.

## Development setup

```bash
./setup.sh
.venv/bin/family-studio doctor
.venv/bin/family-studio serve
```

The server binds to `127.0.0.1:8765`. State, downloaded upstream checkouts and dependencies stay in ignored local directories. Use `STUDIO_DATA` to choose a separate development state directory; do not reuse someone else's running workspace.

## Branches and pull requests

Create a branch for one coherent change, retain unrelated work, and submit a pull request with the problem, resulting behavior and relevant verification. Include screenshots only for intentional public example content. Never commit local state, user media, logs, credentials, private network details or screenshots of other work.

For upstream changes, preserve license and NOTICE files. Update `vendor/sources.lock.json` when intentionally changing vendored files; explain the modification in `THIRD_PARTY.md`. Do not silently update pinned checkouts during unrelated work.

## Style and verification

Follow the surrounding Python and JavaScript style. Validate external input with the existing schema; preserve stable IDs, revision checks, bounded subprocess execution and artifact hashes. Avoid introducing executable code into manifests. Keep CLI results machine-readable, and use actionable errors rather than false success.

Run checks relevant to the change:

```bash
.venv/bin/python -m pytest -q
npm test
npm run build
```

There is no configured standalone linter or coverage command. For export changes, also render a small public example and inspect the affected output format. Passing unit tests alone does not establish rendering quality or feature parity with an upstream application.

## Reporting issues

Include the version or commit, operating system, Python and Node versions, steps, expected behavior and actual behavior. A minimal synthetic manifest is more useful than an entire state directory. Review command output before sharing it: `doctor` is intended for capability checks, while job details can contain local paths. Do not upload personal media, secrets or full logs without removing private content.

## Using Codex

Point Codex at this checkout so it can read `AGENTS.md`. The [agent quickstart](docs/AGENT-QUICKSTART.md) documents CLI patches and MCP. Ask agents to inspect existing revisions, make bounded changes and report verified outcomes. Generated code has the same review, test and attribution requirements as other contributions.
