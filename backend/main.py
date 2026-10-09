import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from oracle_wallet import load_oracle_targets
from config import load_config
from monitor import poll_servers, get_status

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

async def background_poller():
    while True:
        try:
            await asyncio.to_thread(poll_servers)
        except Exception:
            logger.exception('Server poll failed')
        await asyncio.sleep(max(1, int(os.environ.get('MONITOR_POLL_INTERVAL', '60'))))

@asynccontextmanager
async def lifespan(app):
    load_config()  # Fail startup on an invalid/missing imported configuration.
    load_oracle_targets()
    task = asyncio.create_task(background_poller())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

app = FastAPI(title='Monitor API', lifespan=lifespan)

@app.get('/status')
async def read_status():
    return get_status()

@app.get('/health')
async def health_check():
    return {'status': 'ok'}
