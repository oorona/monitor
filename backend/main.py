import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from mcp_server import build_mcp
from status_snapshot import begin_poll, fail_poll
from oracle_wallet import load_oracle_targets
from config import load_config
from monitor import poll_servers, get_status

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

async def background_poller():
    while True:
        begin_poll()
        try:
            await asyncio.to_thread(poll_servers)
        except Exception:
            fail_poll()
            logger.error('Server poll failed; previous observations are stale')
        await asyncio.sleep(max(1, int(os.environ.get('MONITOR_POLL_INTERVAL', '60'))))

@asynccontextmanager
async def lifespan(app):
    load_config()  # Fail startup on an invalid/missing imported configuration.
    load_oracle_targets()
    task = asyncio.create_task(background_poller())
    async with mcp_app.lifespan(app):
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

mcp = build_mcp()
project_host = os.environ.get('MONITOR_PROJECT_HOST', 'localhost')
hosts = list(dict.fromkeys(['localhost', '127.0.0.1', 'monitor-backend', project_host]))
mcp_app = mcp.http_app(path='/', stateless_http=True, host_origin_protection=True, allowed_hosts=hosts,
                       allowed_origins=[os.environ.get('MONITOR_SITE_URL', 'http://localhost:3103')])
app = FastAPI(title='Monitor API', lifespan=lifespan)

@app.middleware('http')
async def normalize_mcp_path(request, call_next):
    if request.scope['path'] == '/mcp':
        request.scope['path'] = '/mcp/'
        request.scope['raw_path'] = b'/mcp/'
    return await call_next(request)

app.mount('/mcp', mcp_app)

@app.get('/status')
async def read_status():
    return get_status()

@app.get('/health')
async def health_check():
    return {'status': 'ok'}
