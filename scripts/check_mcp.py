"""Exercise the real stdio interface with temporary synthetic project data."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]

async def main() -> None:
    with tempfile.TemporaryDirectory(prefix='creative-studio-mcp-') as data:
        env = {k: os.environ[k] for k in ('PATH','LANG','STUDIO_BROWSER','STUDIO_SOURCES') if k in os.environ}
        env['STUDIO_DATA'] = data
        params = StdioServerParameters(command=sys.executable, args=['-m','studio.cli','mcp'], cwd=str(ROOT), env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = [tool.name for tool in (await session.list_tools()).tools]
                assert len(names) == 19, names
                calls = [
                    ('studio_schema', {}),
                    ('studio_recipes', {}),
                    ('studio_create', {'recipe_id':'assembly_story','project_id':'mcp-assembly'}),
                    ('studio_preflight', {'project_id':'mcp-assembly'}),
                    ('studio_patch', {'project_id':'mcp-assembly','expected_revision':1,'operations':[{'op':'set','target':'solid','id':'tray','values':{'bore':16}}]}),
                    ('studio_compare', {'project_id':'mcp-assembly','before':1}),
                    ('studio_assets', {}),
                    ('studio_timeline', {'project_id':'mcp-assembly'}),
                ]
                for name, arguments in calls:
                    result = await session.call_tool(name, arguments)
                    assert not result.is_error, (name, result)
                stale = await session.call_tool('studio_patch', {'project_id':'mcp-assembly','expected_revision':1,'operations':[{'op':'set','target':'solid','id':'tray','values':{'bore':18}}]})
                assert stale.is_error and 'changed before' in str(stale.content)
                print(json.dumps({'transport':'actual stdio MCP','tools':len(names),'create_patch_compare_preflight':True,'stale_revision_rejected':True}))

if __name__ == '__main__':
    asyncio.run(main())
