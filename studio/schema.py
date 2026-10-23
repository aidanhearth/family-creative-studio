"""A bounded, provider-neutral document. No executable code or network references."""
from __future__ import annotations
import hashlib
import json
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
    accent: Color = "#B9432C"
    muted: Color = "#65615B"

class BooleanOperation(Strict):
    operation: Literal["union", "subtract", "intersect"]
    tool: Id

class Solid(Strict):
    """Millimetre geometry; rotation is intrinsic XYZ degrees before translation.

    Torus size is (outer diameter, outer diameter, tube diameter). Extrusion
    profile coordinates span [-.5,.5] in each axis, scaled by size x/y.
    Boolean tools are already-built world-coordinate solids; construction
    solids remain available to operations but are excluded from deliverables.
    """
    id: Id
    name: Text
    kind: Literal["box", "cylinder", "sphere", "cone", "torus", "extrusion", "step"] = "box"
    size: tuple[Positive, Positive, Positive]
    position: tuple[Number, Number, Number] = (0, 0, 0)
    rotation: tuple[Number, Number, Number] = (0, 0, 0)
    color: Color = "#B37B52"
    bore: Annotated[float, Field(allow_inf_nan=False, ge=0, le=500)] = 0
    fillet: Annotated[float, Field(allow_inf_nan=False, ge=0, le=500)] = 0
    chamfer: Annotated[float, Field(allow_inf_nan=False, ge=0, le=500)] = 0
    top_diameter: Annotated[float, Field(allow_inf_nan=False, ge=0, le=1000)] = 0
    profile: list[tuple[Number, Number]] = Field(default_factory=list, max_length=128)
    asset: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}\.step$")
    construction: bool = False
    booleans: list[BooleanOperation] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def geometry_contract(self):
        if self.bore >= min(self.size[0], self.size[1]):
            raise ValueError("The through-hole must fit inside its part")
        if self.kind in ("cylinder", "cone", "torus", "sphere") and self.size[0] != self.size[1]:
            raise ValueError("Circular parts require equal x/y diameters")
        if self.kind == "sphere" and self.size[0] != self.size[2]:
            raise ValueError("A sphere requires three equal diameters")
        if self.kind == "torus" and self.size[2] >= self.size[0] / 2:
            raise ValueError("A ring torus requires tube diameter < outer diameter / 2")
        if self.kind == "cone" and self.top_diameter > self.size[0]:
            raise ValueError("Cone top diameter must not exceed its base diameter")
        if self.kind != "cone" and self.top_diameter:
            raise ValueError("top_diameter applies only to cones")
        if self.fillet and self.chamfer:
            raise ValueError("Choose either all-edge fillet or chamfer")
        if max(self.fillet, self.chamfer) >= min(self.size) / 2:
            raise ValueError("Edge treatment must be smaller than half the narrowest dimension")
        if self.kind == "step" and not self.asset:
            raise ValueError("STEP parts require an imported STEP asset")
        if self.kind != "step" and self.asset:
            raise ValueError("A STEP asset applies only to STEP parts")
        if self.kind == "extrusion":
            from .geometry_profile import validate_profile
            validate_profile(self.profile)
        elif self.profile:
            raise ValueError("A polygon profile applies only to extrusions")
        return self

class VideoSettings(Strict):
    resolution: Literal['source', '720p', '1080p', '2160p'] = 'source'
    fps: Literal['source', 24, 25, 30, 50, 60] = 'source'
    crf: Annotated[int, Field(ge=0, le=28)] = 18
    captions: bool = True
    normalize_audio: bool = True

class SlideSettings(Strict):
    layout: Literal['editorial', 'full', 'split'] = 'editorial'
    narration: bool = True
    autoplay: bool = True
    transition: Literal['fade', 'none'] = 'fade'
    animation: Literal['none', 'fade'] = 'none'

class EffectSettings(Strict):
    enabled: bool = False
    type: Literal['Circle', 'LinearGradient'] = 'Circle'
    color: Color = '#d8cbb8'
    secondary: Color = '#F6F4EF'
    radius: Annotated[float, Field(ge=0, le=2, allow_inf_nan=False)] = .4
    softness: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] = .1
    angle: Annotated[float, Field(ge=-360, le=360, allow_inf_nan=False)] = 0
    opacity: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] = .35

class DiagramSpec(Strict):
    kind: Literal['architecture', 'workflow', 'sequence', 'dataflow', 'lifecycle', 'erd', 'tree', 'class', 'timeline', 'waterfall', 'explainer']
    document: dict

    @model_validator(mode='after')
    def bounded_document(self):
        def walk(value, depth=0):
            if depth > 20:
                raise ValueError('Diagram JSON nesting exceeds 20 levels')
            if isinstance(value, dict):
                if any(not isinstance(key, str) for key in value):
                    raise ValueError('Diagram object keys must be strings')
                for child in value.values():
                    walk(child, depth + 1)
            elif isinstance(value, list):
                for child in value:
                    walk(child, depth + 1)
            elif not isinstance(value, (str, int, float, bool, type(None))):
                raise ValueError('Diagram values must be JSON data')
        walk(self.document)
        if len(json.dumps(self.document, allow_nan=False, ensure_ascii=False).encode()) > 256 * 1024:
            raise ValueError('Diagram JSON exceeds 256 KiB')
        return self

class Visual(Strict):
    mode: Literal['diagram','orbit','explode','image','clip'] = 'diagram'
    asset: str | None = Field(default=None,pattern=r'^[a-f0-9]{64}\.(png|jpg|mp4)$')
    start: Annotated[float,Field(ge=0,le=7200,allow_inf_nan=False)] = 0
    audio: Literal['voice','source','silent','mix'] = 'voice'
    voice_gain: Annotated[float, Field(ge=0, le=2, allow_inf_nan=False)] = 1
    source_gain: Annotated[float, Field(ge=0, le=2, allow_inf_nan=False)] = 1

    @model_validator(mode='after')
    def matching_media(self):
        if self.mode in ('image','clip') and not self.asset:
            raise ValueError('Choose an uploaded asset for this scene')
        if self.asset and (self.mode not in ('image','clip') or (self.mode=='clip')!=self.asset.endswith('.mp4')):
            raise ValueError('Scene type does not match its asset')
        if self.audio in ('source','mix') and self.mode!='clip':
            raise ValueError('Source audio requires a video clip')
        return self

class Beat(Strict):
    id: Id
    title: Annotated[str, Field(min_length=1, max_length=28)]
    body: Annotated[str, Field(min_length=1, max_length=85)]
    narration: Annotated[str, Field(max_length=16384)]
    duration: Annotated[float, Field(ge=.1, le=600, allow_inf_nan=False)] = 6
    focus: list[Id] = Field(default_factory=list, max_length=256)
    visual: Visual = Field(default_factory=Visual)
    layout: Literal['editorial', 'full', 'split'] | None = None
    narration_asset: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}\.wav$")
    svg_asset: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}\.svg$")

    @model_validator(mode='after')
    def narration_bytes(self):
        if len(self.narration.encode('utf-8')) > 16384:
            raise ValueError('Narration must not exceed 16 KiB per chapter')
        if self.svg_asset and self.visual.mode != 'diagram':
            raise ValueError('Native SVG slides use diagram mode; choose a separate chapter for media scenes')
        return self

class Manifest(Strict):
    schema_version: Literal[1] = 1
    id: Id
    title: Annotated[str, Field(min_length=1, max_length=48)]
    subtitle: Annotated[str, Field(min_length=1, max_length=140)]
    brand: Brand = Field(default_factory=Brand)
    video: VideoSettings = Field(default_factory=VideoSettings)
    slides: SlideSettings = Field(default_factory=SlideSettings)
    effect: EffectSettings = Field(default_factory=EffectSettings)
    diagram: DiagramSpec | None = None
    scene_asset: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}\.glb$")
    scene_animation: Annotated[int, Field(ge=0, le=255)] = 0
    solids: list[Solid] = Field(default_factory=list, max_length=256)
    beats: list[Beat] = Field(min_length=1, max_length=256)
    narration_asset: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}\.wav$")
    style_id: str | None = Field(default=None, max_length=80)
    output_targets: list[Literal['web','diagram','cad','slides','video']] = Field(default_factory=lambda:['web','diagram','cad','slides','video'],min_length=1,max_length=5)

    @model_validator(mode="after")
    def cross_refs(self):
        for objects in (self.solids, self.beats):
            ids = [o.id for o in objects]
            if len(ids) != len(set(ids)):
                raise ValueError("IDs must be unique within each collection")
        previous = set()
        for solid in self.solids:
            if any(op.tool not in previous for op in solid.booleans):
                raise ValueError("Boolean tools must refer to preceding solids")
            previous.add(solid.id)
        known = {s.id for s in self.solids if not s.construction}
        if self.solids and not known:
            raise ValueError("At least one CAD part must be a deliverable, not construction")
        if not self.scene_asset and len(known)<2 and any(b.visual.mode=='explode' for b in self.beats):
            raise ValueError('An exploded scene requires at least two solids; use orbit for one part')
        if not self.scene_asset and not known and any(b.visual.mode in ('orbit','explode') for b in self.beats):
            raise ValueError('A moving 3D scene requires at least one solid')
        if any(b.visual.audio in ('voice','mix') and not b.narration.strip() and not (b.narration_asset or self.narration_asset) for b in self.beats):
            raise ValueError('Narration text is required for voice scenes')
        if len(self.output_targets)!=len(set(self.output_targets)):
            raise ValueError('Output targets must be unique')
        if any(set(b.focus) - known for b in self.beats):
            raise ValueError("A beat refers to a missing solid")
        if self.scene_asset and any(b.focus for b in self.beats):
            raise ValueError('Imported scenes use their complete hierarchy; clear CAD part focus')
        if sum(b.duration for b in self.beats) > 7200:
            raise ValueError("A local render is limited to 7200 seconds")
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
