import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from monitor import poll_servers, get_status
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Server Monitor API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Start the background polling task."""
    asyncio.create_task(background_poller())

async def background_poller():
    """Runs the poll_servers function periodically."""
    while True:
        logger.info("Starting server poll...")
        try:
            # Run the synchronous poll_servers in a thread to not block the event loop
            await asyncio.to_thread(poll_servers)
        except Exception as e:
            logger.error(f"Error in background poller: {e}")
        
        # Poll every 60 seconds (configurable?)
        await asyncio.sleep(60)

@app.get("/status")
async def read_status():
    """Returns the current status of all servers."""
    return get_status()

@app.get("/health")
async def health_check():
    return {"status": "ok"}
