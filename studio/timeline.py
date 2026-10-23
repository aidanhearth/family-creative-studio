"""Editable, lossless timeline interchange with revision protection."""
from typing import Literal
from pydantic import Field
from .schema import Strict, Beat, Manifest, VideoSettings, SlideSettings
from .store import Conflict


class Timeline(Strict):
    format: Literal['family-studio-timeline'] = 'family-studio-timeline'
    version: Literal[1] = 1
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    video: VideoSettings
    slides: SlideSettings
    segments: list[Beat] = Field(min_length=1, max_length=256)


def export_timeline(store, project_id):
    project = store.project(project_id)
    manifest = Manifest.model_validate(project['manifest'])
    result = Timeline(source_sha256=manifest.digest(), video=manifest.video,
                      slides=manifest.slides, segments=manifest.beats)
    return {'project_id': project_id, 'revision': project['revision'], 'timeline': result.model_dump(),
            'timing': 'Authored clip trims and scene duration; render EDL records actual audio-adjusted timing.'}


def import_timeline(store, project_id, expected_revision, timeline, dry_run=False):
    project = store.project(project_id)
    before = Manifest.model_validate(project['manifest'])
    if project['revision'] != expected_revision:
        raise Conflict('Project changed before timeline import')
    timeline = Timeline.model_validate(timeline)
    if timeline.source_sha256 != before.digest():
        raise Conflict('Timeline was exported from a different manifest; re-export before editing')
    data = before.model_dump()
    data.update(beats=[b.model_dump() for b in timeline.segments], video=timeline.video.model_dump(), slides=timeline.slides.model_dump())
    after = Manifest.model_validate(data)
    after.resolved()
    from .media_assets import preflight
    preflight(store, after, after.output_targets)
    from .operations import changes_between
    changes = changes_between(before.model_dump(), after.model_dump())
    if dry_run:
        return {'saved': False, 'manifest': after.model_dump(), 'changes': changes, 'revision': expected_revision}
    return {**store.save(after, expected_revision), 'saved': True, 'changes': changes}
