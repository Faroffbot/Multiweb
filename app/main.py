from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.config import DOWNLOADS_DIR
from app.routers import download


@asynccontextmanager
async def lifespan(app: FastAPI):
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Video Downloader",
    description="Download videos using yt-dlp with aria2c multi-chunk support",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(download.router)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

if DOWNLOADS_DIR.exists():
    app.mount("/downloads", StaticFiles(directory=str(DOWNLOADS_DIR)), name="downloads")


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = Path(__file__).parent.parent / "frontend" / "index.html"
    if index_path.exists():
        return index_path.read_text()
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Video Downloader</title>
    </head>
    <body>
        <h1>Video Downloader API is running</h1>
        <p>API endpoints available at /api</p>
    </body>
    </html>
    """


@app.get("/health")
async def health_check():
    return {"status": "healthy"}