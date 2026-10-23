"""Atomic edits addressed by stable object IDs, with full manifest validation."""
from __future__ import annotations
import copy
import re
from typing import Literal
from pydantic import Field
from .schema import Manifest,Strict,Id
from .store import Conflict

class Operation(Strict):
    op: Literal['set','add','remove','move']
    target: Literal['project','brand','solid','beat']
    id: Id | None = None
    values: dict = Field(default_factory=dict)
    index: int | None = Field(default=None,ge=0,le=15)

def changes_between(before,after,path=''):
    if isinstance(before,dict) and isinstance(after,dict):
        return [x for k in sorted(before.keys()|after.keys()) for x in changes_between(before.get(k),after.get(k),(path+'.'+k).strip('.'))]
    if isinstance(before,list) and isinstance(after,list) and all(isinstance(x,dict) and 'id' in x for x in before+after):
        a={x['id']:x for x in before};b={x['id']:x for x in after}
        diff=changes_between(a,b,path)
        if list(a)!=list(b):diff.append({'path':path+'.order','before':list(a),'after':list(b)})
        return diff
    return [] if before==after else [{'path':path,'before':before,'after':after}]

def apply_operations(manifest:Manifest,operations:list[dict|Operation]):
    if not 1<=len(operations)<=64:raise ValueError('Use 1–64 operations per atomic edit')
    data=copy.deepcopy(manifest.model_dump())
    for raw in operations:
        op=raw if isinstance(raw,Operation) else Operation.model_validate(raw)
        if op.target in ('project','brand'):
            if op.op!='set' or op.id is not None:raise ValueError('Project/brand edits use set without an object ID')
            target=data if op.target=='project' else data['brand']
            allowed={'title','subtitle','narration_asset','style_id','output_targets'} if op.target=='project' else {'name','paper','ink','accent','muted'}
            if not op.values or set(op.values)-allowed:raise ValueError('Unsupported project/brand field')
            target.update(op.values);continue
        key={'solid':'solids','beat':'beats'}[op.target];items=data[key]
        if op.op=='add':
            if op.id is not None or 'id' not in op.values:raise ValueError('Add supplies the new stable ID in values')
            at=len(items) if op.index is None else op.index
            if at>len(items):raise ValueError('Insertion position is outside the collection')
            items.insert(at,copy.deepcopy(op.values));continue
        matches=[i for i,x in enumerate(items) if x['id']==op.id]
        if not matches:raise ValueError(f'Unknown {op.target} ID: {op.id}')
        at=matches[0]
        if op.op=='set':
            if not op.values or 'id' in op.values:raise ValueError('Set preserves the stable object ID')
            items[at].update(copy.deepcopy(op.values))
        elif op.op=='move':
            if op.index is None or op.index>=len(items):raise ValueError('Choose a valid destination position')
            items.insert(op.index,items.pop(at))
        elif op.op=='remove':
            if op.target=='solid':
                solid=items[at];lookup={'width':solid['size'][0],'depth':solid['size'][1],'height':solid['size'][2],'bore':solid['bore']}
                lookup={k:f'{v:g}' for k,v in lookup.items()};lookup['size']='×'.join(f'{v:g}' for v in solid['size'])
                pattern=re.compile(r'\{\{'+re.escape(op.id)+r'\.(size|width|depth|height|bore)\}\}')
                def freeze(text):return pattern.sub(lambda m:lookup[m[1]],text)
                for name in ('title','subtitle'):data[name]=freeze(data[name])
                for beat in data['beats']:
                    beat['focus']=[x for x in beat['focus'] if x!=op.id]
                    for name in ('title','body','narration'):beat[name]=freeze(beat[name])
            items.pop(at)
    result=Manifest.model_validate(data);result.resolved()
    return result

def patch_project(store,project_id,expected_revision,operations,*,dry_run=False):
    project=store.project(project_id)
    if project['revision']!=expected_revision:raise Conflict('Project changed before the atomic edit')
    before=Manifest.model_validate(project['manifest']);after=apply_operations(before,operations)
    diff=changes_between(before.model_dump(),after.model_dump())
    if dry_run:return {'project_id':project_id,'revision':expected_revision,'changes':diff,'manifest':after.model_dump(),'saved':False}
    result=store.save(after,expected_revision) if diff else project
    return {**result,'changes':diff,'saved':bool(diff)}
