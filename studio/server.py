from __future__ import annotations
from contextlib import asynccontextmanager
import json
import asyncio
import secrets
import subprocess
import sys
from urllib.parse import urlsplit
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import FileResponse,JSONResponse
from pydantic import BaseModel,Field
from .paths import ROOT,contained
from .schema import Manifest,TARGETS
from .store import Store,Conflict
from .diagnostics import doctor

class SaveRequest(BaseModel):
    manifest: Manifest
    expected_revision:int|None=None

class RunRequest(BaseModel):
    targets:list[str]|None=None
    force:bool=False
    expected_revision:int|None=None

from .operations import Operation,patch_project
class PatchRequest(BaseModel):
    expected_revision:int
    operations:list[Operation]=Field(min_length=1,max_length=2048)
    dry_run:bool=False
class CreateRequest(BaseModel):
    recipe_id:str
    project_id:str
    title:str|None=None

class PreviewRequest(BaseModel):
    manifest:Manifest

class TimelineRequest(BaseModel):
    expected_revision:int
    timeline:dict
    dry_run:bool=False

def create_app():
    from .provenance import runtime_sources
    runtime_sources()
    store=Store();token=secrets.token_urlsafe(32)
    @asynccontextmanager
    async def lifespan(app):
        from .worker import worker_alive
        worker=None
        with (store.root/'service-worker.log').open('ab') as log:
            async def supervise():
                nonlocal worker
                while True:
                    if (worker is None or worker.poll() is not None) and not worker_alive(store.root):
                        worker=subprocess.Popen([sys.executable,'-m','studio.worker'],cwd=ROOT,stdout=log,stderr=log)
                    await asyncio.sleep(1)
            task=asyncio.create_task(supervise())
            try: yield
            finally:
                task.cancel()
                try: await task
                except asyncio.CancelledError: pass
                if worker is not None and worker.poll() is None:
                    worker.terminate()
                    try: await asyncio.to_thread(worker.wait,timeout=8)
                    except subprocess.TimeoutExpired:worker.kill();await asyncio.to_thread(worker.wait)
    app=FastAPI(title='Family Creative Studio',lifespan=lifespan,docs_url=None,redoc_url=None)
    @app.middleware('http')
    async def local_guard(request:Request,call_next):
        host=request.headers.get('host','')
        try:parsed=urlsplit('http://'+host)
        except ValueError:return JSONResponse({'error':'invalid host'},400)
        if parsed.hostname not in ('127.0.0.1','localhost'):
            return JSONResponse({'error':'loopback host required'},403)
        origin=request.headers.get('origin')
        if origin and origin not in ('http://'+host,'https://'+host):
            return JSONResponse({'error':'same-origin required'},403)
        if request.method not in ('GET','HEAD','OPTIONS') and not secrets.compare_digest(request.headers.get('x-studio-token',''),token):
            return JSONResponse({'error':'studio token required'},403)
        limit=512*1024*1024 if request.url.path in ('/api/media','/api/audio') else 50*1024*1024 if request.url.path in ('/api/cad','/api/scene') else 2*1024*1024 if request.url.path=='/api/svg' else 16*1024*1024
        try:
            if int(request.headers.get('content-length','0'))>limit:return JSONResponse({'error':'request too large'},413)
        except ValueError:return JSONResponse({'error':'invalid content length'},400)
        if request.method not in ('GET','HEAD','OPTIONS') and request.url.path not in ('/api/audio','/api/media','/api/cad','/api/scene','/api/svg'):
            chunks=[]; total=0
            async for chunk in request.stream():
                total+=len(chunk)
                if total>limit:return JSONResponse({'error':'request too large'},413)
                chunks.append(chunk)
            # Starlette CachedRequest forwards this verified cached body to the downstream app.
            request._body=b''.join(chunks)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        policy="default-src 'self' data: blob:; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'self'; object-src 'none'"
        if request.url.path.startswith('/artifacts/'):
            policy="sandbox allow-scripts; "+policy.replace("script-src 'self'", "script-src 'self' 'unsafe-inline'")
        response.headers['Content-Security-Policy']=policy
        return response
    @app.exception_handler(KeyError)
    async def missing(request,error):return JSONResponse({'error':str(error)},404)
    @app.exception_handler(Conflict)
    async def conflict(request,error):return JSONResponse({'error':str(error)},409)
    @app.exception_handler(ValueError)
    async def invalid(request,error):return JSONResponse({'error':str(error)},422)
    @app.get('/')
    def index():return FileResponse(ROOT/'web/index.html')
    @app.get('/static/{name}')
    def static(name:str):
        options={'app.js':ROOT/'dist/app.js','app.css':ROOT/'web/app.css','impeccable.js':ROOT/'vendor/pbakaus--impeccable/impeccable.js'}
        if name not in options:raise HTTPException(404)
        return FileResponse(options[name])
    @app.get('/api/session')
    def session():return {'token':token,'copy':json.loads((ROOT/'web/copy.json').read_text()),'capabilities':doctor(),'upgrade':json.loads((ROOT/'web/upgrade-copy.json').read_text())}
    @app.get('/api/schema')
    def schema():return Manifest.model_json_schema()
    @app.get('/api/recipes')
    def recipes():
        from .recipes import recipes
        return recipes()
    @app.post('/api/create')
    def create(body:CreateRequest):
        from .recipes import create_project
        return create_project(store,body.recipe_id,body.project_id,body.title)
    @app.post('/api/projects/{project_id}/patch')
    def patch(project_id:str,body:PatchRequest):return patch_project(store,project_id,body.expected_revision,body.operations,dry_run=body.dry_run)
    @app.get('/api/projects/{project_id}/compare')
    def compare(project_id:str,before:int,after:int|None=None):return store.compare(project_id,before,after)
    @app.get('/api/projects/{project_id}/timeline')
    def timeline_export(project_id:str):
        from .timeline import export_timeline
        return export_timeline(store,project_id)
    @app.put('/api/projects/{project_id}/timeline')
    def timeline_import(project_id:str,body:TimelineRequest):
        from .timeline import import_timeline
        return import_timeline(store,project_id,body.expected_revision,body.timeline,body.dry_run)
    @app.post('/api/geometry/preview')
    def geometry_preview(body:PreviewRequest):
        from .geometry_preview import preview_geometry
        return preview_geometry(store,body.manifest)
    @app.get('/api/previews/{key}/{name}')
    def preview_file(key:str,name:str):
        import re
        if not re.fullmatch(r'[a-f0-9]{64}',key) or name not in ('model.glb','geometry.json'):raise HTTPException(404)
        from .geometry_preview import preview_file_path
        try:path=preview_file_path(store,key,name)
        except ValueError as error:raise HTTPException(409,str(error)) from error
        if not path.is_file():raise HTTPException(404)
        return FileResponse(path)
    @app.post('/api/cad')
    async def cad_import(request:Request):
        from .cad_assets import import_cad,CAD_LIMIT
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>CAD_LIMIT:raise HTTPException(413)
        return await asyncio.to_thread(import_cad,store,bytes(data),request.query_params.get('name'))
    @app.post('/api/scene')
    async def scene_import(request:Request):
        from .scene_assets import import_scene,SCENE_LIMIT
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>SCENE_LIMIT:raise HTTPException(413)
        return await asyncio.to_thread(import_scene,store,bytes(data),request.query_params.get('name'))
    @app.post('/api/svg')
    async def svg_import(request:Request):
        from .svg_assets import import_svg,SVG_LIMIT
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>SVG_LIMIT:raise HTTPException(413)
        return import_svg(store,bytes(data),request.query_params.get('name'))
    @app.get('/api/projects/{project_id}/preflight')
    def preflight(project_id:str):
        from .media_assets import preflight
        m=Manifest.model_validate(store.project(project_id)['manifest'])
        from .preflight import contrast_checks
        return {**preflight(store,m,m.output_targets),'contrast':contrast_checks(m)}
    @app.post('/api/media')
    async def media(request:Request):
        from .media_assets import import_media,LIMIT
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>LIMIT:raise HTTPException(413)
        return await asyncio.to_thread(import_media,store,bytes(data),request.query_params.get('name'))
    @app.get('/api/assets')
    def assets():
        return [json.loads(p.read_text()) for p in sorted((store.root/'assets').glob('*.json'))]
    @app.get('/api/assets/{name}')
    def asset(name:str):
        from .agent_assets import asset_path
        path=asset_path(store,name)
        return FileResponse(path)
    @app.get('/api/projects')
    def projects():return store.projects()
    @app.post('/api/demo')
    def demo():
        from .seed import demo as seed
        document=seed()
        try:return store.project(document.id)
        except KeyError:return store.save(document)
    @app.get('/api/projects/{project_id}')
    def project(project_id:str):return store.project(project_id)
    @app.post('/api/validate')
    def validate(manifest:Manifest):
        manifest.resolved()
        return manifest.model_dump()
    @app.post('/api/projects')
    def save(body:SaveRequest):
        body.manifest.resolved()
        return store.save(body.manifest,body.expected_revision)
    @app.post('/api/projects/{project_id}/render')
    def render(project_id:str,body:RunRequest):return store.enqueue(project_id,body.targets,force=body.force,expected_revision=body.expected_revision)
    @app.get('/api/jobs')
    def jobs(project_id:str|None=None):return store.jobs(project_id)
    @app.get('/api/jobs/{job_id}')
    def job(job_id:str):return store.job(job_id)
    @app.post('/api/jobs/{job_id}/cancel')
    def cancel(job_id:str):return store.cancel(job_id)
    @app.post('/api/jobs/{job_id}/retry')
    def retry(job_id:str):return store.retry(job_id)
    @app.post('/api/audio')
    async def audio(request:Request):
        from .assets import import_audio,AUDIO_LIMIT
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>AUDIO_LIMIT:raise HTTPException(413)
        return await asyncio.to_thread(import_audio,store,bytes(data),request.query_params.get('name'))
    @app.get('/api/styles')
    def styles():return json.loads((ROOT/'vendor/freestylefly--awesome-gpt-image-2/styles.json').read_text())
    @app.get('/artifacts/{job_id}/{name:path}')
    def artifact(job_id:str,name:str):
        job=store.job(job_id)
        if job['state']!='succeeded' or not any(a['path']==name for a in job['artifacts'] or []):raise HTTPException(404)
        path=contained(store.artifact_root(job),name)
        if not path.is_file():raise HTTPException(404)
        return FileResponse(path)
    return app
