from __future__ import annotations
import argparse
import os
import json
from pathlib import Path
import subprocess
import sys
import time
from .paths import ROOT,SOURCES
from .schema import Manifest,TARGETS
from .store import Store

def ensure_worker(store):
    env = dict(os.environ, STUDIO_DATA=str(store.root.resolve()), STUDIO_SOURCES=str(SOURCES))
    if 'STUDIO_BROWSER' in env:
        from .runtime import browser_executable
        env['STUDIO_BROWSER'] = browser_executable()
    with (store.root/'worker.log').open('ab') as log:
        subprocess.Popen([sys.executable,'-m','studio.worker','--once'],cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=True)

def main():
    p=argparse.ArgumentParser(prog='family-studio',description='Local manifest-driven creative workbench; JSON output for every agent.')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('demo');sub.add_parser('projects');sub.add_parser('doctor');sub.add_parser('sources');sub.add_parser('mcp')
    get=sub.add_parser('get');get.add_argument('id');get.add_argument('--manifest',action='store_true')
    imp=sub.add_parser('save');imp.add_argument('file',type=Path);imp.add_argument('--revision',type=int)
    run=sub.add_parser('render');run.add_argument('id');run.add_argument('--targets',nargs='+',default=None,choices=TARGETS);run.add_argument('--wait',action='store_true');run.add_argument('--force',action='store_true');run.add_argument('--timeout',type=float,default=900)
    for command in ('status','cancel','retry'):
        c=sub.add_parser(command);c.add_argument('id')
    for command in ('audio','media','cad','scene','svg'):
        a=sub.add_parser(command);a.add_argument('file',type=Path)
    sub.add_parser('schema');sub.add_parser('recipes')
    c=sub.add_parser('create');c.add_argument('recipe');c.add_argument('id');c.add_argument('--title')
    c=sub.add_parser('patch');c.add_argument('id');c.add_argument('file',type=Path);c.add_argument('--revision',type=int,required=True);c.add_argument('--dry-run',action='store_true')
    c=sub.add_parser('compare');c.add_argument('id');c.add_argument('before',type=int);c.add_argument('--after',type=int)
    c=sub.add_parser('preflight');c.add_argument('id')
    c=sub.add_parser('timeline');c.add_argument('id')
    c=sub.add_parser('timeline-import');c.add_argument('id');c.add_argument('file',type=Path);c.add_argument('--revision',type=int,required=True);c.add_argument('--dry-run',action='store_true')
    sub.add_parser('assets')
    serve=sub.add_parser('serve');serve.add_argument('--port',type=int,default=8765);serve.add_argument('--socket',type=Path)
    args=p.parse_args()
    try:
        store=Store();result=None
        if args.command=='demo':
            from .seed import demo
            doc=demo()
            try:result=store.project(doc.id)
            except KeyError:result=store.save(doc)
        elif args.command=='projects':result=store.projects()
        elif args.command=='get':
            result=store.project(args.id)
            if args.manifest:result=result['manifest']
        elif args.command=='save':
            raw=sys.stdin.read(16*1024*1024+1) if str(args.file)=='-' else args.file.read_text(encoding='utf-8')
            if len(raw.encode())>16*1024*1024:raise ValueError('Manifest exceeds 16 MiB')
            doc=Manifest.model_validate_json(raw);doc.resolved();result=store.save(doc,args.revision)
        elif args.command=='render':
            result=store.enqueue(args.id,args.targets,force=args.force)
            if result['state']=='queued':ensure_worker(store)
            if args.wait:
                deadline=time.monotonic()+args.timeout
                while result['state'] in ('queued','running'):
                    if time.monotonic()>deadline:raise ValueError('Wait timed out; job continues. Check status '+result['id'])
                    time.sleep(.5);result=store.job(result['id'])
                if result['state']!='succeeded':
                    print(json.dumps(result,ensure_ascii=False));return 1
        elif args.command=='status':result=store.job(args.id)
        elif args.command=='cancel':result=store.cancel(args.id)
        elif args.command=='retry':result=store.retry(args.id);ensure_worker(store)
        elif args.command=='doctor':
            from .diagnostics import doctor
            result=doctor()
        elif args.command=='sources':
            from .provenance import sources
            result=sources()
        elif args.command=='schema':result=Manifest.model_json_schema()
        elif args.command=='recipes':
            from .recipes import recipes
            result=recipes()
        elif args.command=='create':
            from .recipes import create_project
            result=create_project(store,args.recipe,args.id,args.title)
        elif args.command=='patch':
            from .operations import Operation,patch_project
            raw=sys.stdin.read(16*1024*1024+1) if str(args.file)=='-' else args.file.read_text()
            if len(raw.encode())>16*1024*1024:raise ValueError('Patch exceeds 16 MiB')
            result=patch_project(store,args.id,args.revision,[Operation.model_validate(o) for o in json.loads(raw)],dry_run=args.dry_run)
        elif args.command=='compare':result=store.compare(args.id,args.before,args.after)
        elif args.command=='preflight':
            from .media_assets import preflight
            m=Manifest.model_validate(store.project(args.id)['manifest']);result=preflight(store,m,m.output_targets)
            from .preflight import contrast_checks
            result['contrast']=contrast_checks(m)
        elif args.command=='assets':result=[json.loads(p.read_text()) for p in sorted((store.root/'assets').glob('*.json'))]
        elif args.command=='timeline':
            from .timeline import export_timeline
            result=export_timeline(store,args.id)
        elif args.command=='timeline-import':
            from .timeline import import_timeline
            raw=sys.stdin.read(16*1024*1024+1) if str(args.file)=='-' else args.file.read_text()
            if len(raw.encode())>16*1024*1024:raise ValueError('Timeline exceeds 16 MiB')
            parsed=json.loads(raw);result=import_timeline(store,args.id,args.revision,parsed.get('timeline',parsed),args.dry_run)
        elif args.command in ('cad','scene','svg'):
            if args.command=='cad':
                from .cad_assets import import_cad as importer,CAD_LIMIT as limit
            elif args.command=='scene':
                from .scene_assets import import_scene as importer,SCENE_LIMIT as limit
            else:
                from .svg_assets import import_svg as importer,SVG_LIMIT as limit
            with (args.file.open('rb') if str(args.file)!='-' else __import__('contextlib').nullcontext(sys.stdin.buffer)) as stream:
                result=importer(store,stream.read(limit+1),args.file.name)
        elif args.command=='media':
            from .media_assets import import_media,LIMIT
            with (args.file.open('rb') if str(args.file)!='-' else __import__('contextlib').nullcontext(sys.stdin.buffer)) as stream:
                result=import_media(store,stream.read(LIMIT+1),args.file.name)
        elif args.command=='audio':
            from .assets import import_audio,AUDIO_LIMIT
            with (args.file.open('rb') if str(args.file)!='-' else __import__('contextlib').nullcontext(sys.stdin.buffer)) as stream:
                result=import_audio(store,stream.read(AUDIO_LIMIT+1),args.file.name)
        elif args.command=='mcp':
            from .mcp_server import server
            server.run(transport='stdio');return 0
        elif args.command=='serve':
            import uvicorn
            from .server import create_app
            if args.socket:
                import socket
                from .paths import contained
                path=contained(store.root,str(args.socket.resolve().relative_to(store.root)))
                if path.exists():
                    import stat
                    if not stat.S_ISSOCK(path.stat().st_mode):raise ValueError('Socket path exists and is not a socket')
                    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as probe:
                        probe.settimeout(.2)
                        try:probe.connect(str(path))
                        except ConnectionRefusedError:path.unlink()
                        else:raise ValueError('Studio socket is already serving; use the existing service')
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
                    sock.bind(str(path));path.chmod(0o600)
                    uvicorn.run(create_app(),fd=sock.fileno())
            else:
                uvicorn.run(create_app(),host='127.0.0.1',port=args.port)
            return 0
        if isinstance(result,dict) and result.get('state')=='succeeded':
            result['output_dir']=str(store.artifact_root(result))
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (ValueError,KeyError,OSError) as error:
        print(json.dumps({'error':type(error).__name__,'message':str(error)},ensure_ascii=False));return 2

if __name__=='__main__':sys.exit(main())
