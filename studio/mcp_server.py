from mcp.server.mcpserver import MCPServer
from .store import Store
from .schema import Manifest,TARGETS
from .cli import ensure_worker
from .diagnostics import doctor
from functools import wraps
from mcp.server.mcpserver.exceptions import ToolError
server=MCPServer('Family Creative Studio')

def expected_errors(fn):
    @wraps(fn)
    def call(*args,**kwargs):
        try:return fn(*args,**kwargs)
        except (ValueError,KeyError) as error:raise ToolError(str(error)) from error
    return call

@server.tool()
@expected_errors
def studio_capabilities() -> dict:
    """Inspect local availability, limitations and storage without starting a render."""
    return doctor()

@server.tool()
@expected_errors
def studio_projects() -> list:
    """List saved creative projects."""
    return Store().projects()

@server.tool()
@expected_errors
def studio_get(project_id:str) -> dict:
    """Read a manifest and revision before editing; dimension placeholders stay linked."""
    return Store().project(project_id)

@server.tool()
@expected_errors
def studio_save(manifest:dict,expected_revision:int|None=None) -> dict:
    """Create/update a bounded declarative manifest; updates require the last read revision."""
    document=Manifest.model_validate(manifest);document.resolved()
    return Store().save(document,expected_revision)

@server.tool()
@expected_errors
def studio_render(project_id:str,targets:list[str]|None=None,force:bool=False) -> dict:
    """Queue actual web/SVG/CAD/PPTX/MP4 exports; returns a job ID, never fabricated completion."""
    store=Store();job=store.enqueue(project_id,targets,force=force)
    if job['state']=='queued':ensure_worker(store)
    return job

@server.tool()
@expected_errors
def studio_status(job_id:str) -> dict:
    """Get job status plus verified artifact references after publication."""
    store=Store();job=store.job(job_id)
    if job['state']=='succeeded':job['output_dir']=str(store.artifact_root(job))
    return job

@server.tool()
@expected_errors
def studio_cancel(job_id:str) -> dict:
    """Cancel this queued/running render while retaining previous completed output."""
    return Store().cancel(job_id)

@server.tool()
@expected_errors
def studio_retry(job_id:str) -> dict:
    """Retry the same immutable snapshot after failure or interruption."""
    store=Store();job=store.retry(job_id);ensure_worker(store);return job

@server.tool()
@expected_errors
def studio_schema() -> dict:
    """Discover bounded document fields, enum choices, and geometry limits."""
    return Manifest.model_json_schema()

@server.tool()
@expected_errors
def studio_recipes() -> list:
    """Discover validated starts: product_explainer, assembly_story, media_story."""
    from .recipes import recipes
    return recipes()

@server.tool()
@expected_errors
def studio_create(recipe_id:str,project_id:str,title:str|None=None) -> dict:
    """Create a new project from a recipe; never overwrite an existing ID."""
    from .recipes import create_project
    return create_project(Store(),recipe_id,project_id,title)

@server.tool()
@expected_errors
def studio_patch(project_id:str,expected_revision:int,operations:list[dict],dry_run:bool=False) -> dict:
    """Atomically set/add/remove/move stable-ID project/brand/solid/beat fields. Example: [{"op":"set","target":"solid","id":"tray","values":{"bore":64}}]. Dry run returns a diff without saving."""
    from .operations import Operation,patch_project
    return patch_project(Store(),project_id,expected_revision,[Operation.model_validate(o) for o in operations],dry_run=dry_run)

@server.tool()
@expected_errors
def studio_compare(project_id:str,before:int,after:int|None=None) -> dict:
    """Compare retained revisions: dimensions, text, media and geometry change indicator."""
    return Store().compare(project_id,before,after)

@server.tool()
@expected_errors
def studio_preflight(project_id:str) -> dict:
    """Validate scene assets and trim ranges before spending time rendering."""
    from .media_assets import preflight
    store=Store();m=Manifest.model_validate(store.project(project_id)['manifest'])
    return preflight(store,m,m.output_targets)
