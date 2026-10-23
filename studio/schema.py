"""A bounded, provider-neutral document. No executable code or network references."""
from __future__ import annotations
import hashlib
import json
import math
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,47}$")]
Text = Annotated[str, Field(min_length=1, max_length=200)]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Number = Annotated[float, Field(allow_inf_nan=False, ge=-2000, le=2000)]
Positive = Annotated[float, Field(allow_inf_nan=False, gt=0, le=1000)]

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

class Brand(Strict):
    name: Text = "暖紙社論"
    paper: Color = "#F6F4EF"
    ink: Color = "#18181B"
    accent: Color = "#C84B31"
    muted: Color = "#65615B"

class Solid(Strict):
    id: Id
    name: Text
    kind: Literal["box", "cylinder"] = "box"
    size: tuple[Positive, Positive, Positive]
    position: tuple[Number, Number, Number] = (0, 0, 0)
    color: Color = "#B37B52"
    bore: Annotated[float, Field(allow_inf_nan=False, ge=0, le=500)] = 0

    @model_validator(mode="after")
    def valid_bore(self):
        if self.bore >= min(self.size[0], self.size[1]):
            raise ValueError("The through-hole must fit inside its part")
        if self.kind == "cylinder" and self.size[0] != self.size[1]:
            raise ValueError("A cylinder requires equal x/y diameters")
        return self

class Visual(Strict):
    mode: Literal['diagram','orbit','explode','image','clip'] = 'diagram'
    asset: str | None = Field(default=None,pattern=r'^[a-f0-9]{64}\.(png|jpg|mp4)$')
    start: Annotated[float,Field(ge=0,le=120,allow_inf_nan=False)] = 0
    audio: Literal['voice','source','silent'] = 'voice'

    @model_validator(mode='after')
    def matching_media(self):
        if self.mode in ('image','clip') and not self.asset:
            raise ValueError('Choose an uploaded asset for this scene')
        if self.asset and (self.mode not in ('image','clip') or (self.mode=='clip')!=self.asset.endswith('.mp4')):
            raise ValueError('Scene type does not match its asset')
        if self.audio=='source' and self.mode!='clip':
            raise ValueError('Source audio requires a video clip')
        return self

class Beat(Strict):
    id: Id
    title: Annotated[str, Field(min_length=1, max_length=28)]
    body: Annotated[str, Field(min_length=1, max_length=85)]
    narration: Annotated[str, Field(max_length=300)]
    duration: Annotated[float, Field(ge=3, le=30, allow_inf_nan=False)] = 6
    focus: list[Id] = Field(default_factory=list, max_length=16)
    visual: Visual = Field(default_factory=Visual)

class Manifest(Strict):
    schema_version: Literal[1] = 1
    id: Id
    title: Annotated[str, Field(min_length=1, max_length=48)]
    subtitle: Annotated[str, Field(min_length=1, max_length=140)]
    brand: Brand = Field(default_factory=Brand)
    solids: list[Solid] = Field(default_factory=list, max_length=16)
    beats: list[Beat] = Field(min_length=1, max_length=8)
    narration_asset: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}\.wav$")
    style_id: str | None = Field(default=None, max_length=80)
    output_targets: list[Literal['web','diagram','cad','slides','video']] = Field(default_factory=lambda:['web','diagram','cad','slides','video'],min_length=1,max_length=5)

    @model_validator(mode="after")
    def cross_refs(self):
        for objects in (self.solids, self.beats):
            ids = [o.id for o in objects]
            if len(ids) != len(set(ids)):
                raise ValueError("IDs must be unique within each collection")
        known = {s.id for s in self.solids}
        if len(known)<2 and any(b.visual.mode=='explode' for b in self.beats):
            raise ValueError('An exploded scene requires at least two solids; use orbit for one part')
        if not known and any(b.visual.mode in ('orbit','explode') for b in self.beats):
            raise ValueError('A moving 3D scene requires at least one solid')
        if any(b.visual.audio=='voice' and not b.narration.strip() for b in self.beats):
            raise ValueError('Narration text is required for voice scenes')
        if self.narration_asset and any(b.visual.audio=='source' for b in self.beats):
            raise ValueError('Choose imported narration or source audio; do not mix both modes')
        if len(self.output_targets)!=len(set(self.output_targets)):
            raise ValueError('Output targets must be unique')
        if any(set(b.focus) - known for b in self.beats):
            raise ValueError("A beat refers to a missing solid")
        if sum(b.duration for b in self.beats) > 120:
            raise ValueError("A local render is limited to 120 seconds")
        return self

    def resolved(self):
        import re
        lookup = {}
        for solid in self.solids:
            lookup[solid.id + '.size'] = '×'.join(f'{v:g}' for v in solid.size)
            for key, value in zip(('width','depth','height'), solid.size):
                lookup[solid.id + '.' + key] = f'{value:g}'
            lookup[solid.id + '.bore'] = f'{solid.bore:g}'
        def expand(text):
            def sub(match):
                if match[1] not in lookup:
                    raise ValueError('Unknown dimension token: ' + match[1])
                return lookup[match[1]]
            return re.sub(r'\{\{([a-z0-9_.-]+)\}\}', sub, text)
        data = self.model_dump()
        for key in ('title', 'subtitle'):
            data[key] = expand(data[key])
        for beat in data['beats']:
            for key in ('title','body','narration'):
                beat[key] = expand(beat[key])
        return Manifest.model_validate(data)

    def canonical(self) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def digest(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()

TARGETS = ("web", "diagram", "cad", "slides", "video")

def targets_checked(values: list[str]) -> list[str]:
    if not values or set(values) - set(TARGETS):
        raise ValueError("Choose web, diagram, cad, slides or video")
    return sorted(set(values))

def score_checked(value: float | str, minimum=0.0, maximum=1.0) -> float:
    """The img2threejs review contract must reject NaN/Infinity before comparing."""
    if isinstance(value, bool):
        raise ValueError("Boolean is not a quality score")
    score = float(value)
    if not math.isfinite(score) or not minimum <= score <= maximum:
        raise ValueError("Quality scores must be finite and in range")
    return score
