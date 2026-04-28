import json
import os
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.config import DOWNLOADS_DIR
from app.core.downloader import downloader
from app.core.websocket import ws_manager
from app.schemas.download import (
    DownloadRequest,
    DownloadResponse,
    FileInfo,
    JobStatusResponse,
    VideoInfoResponse,
)

router = APIRouter(prefix="/api", tags=["download"])


@router.get("/")
async def root():
    return {"status": "ok", "message": "Video Downloader API"}


@router.post("/info", response_model=VideoInfoResponse)
async def get_video_info(request: DownloadRequest):
    try:
        info = await downloader.get_video_info(str(request.url))
        return VideoInfoResponse(**info.to_dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get video info: {str(e)}")


@router.post("/download", response_model=DownloadResponse)
async def start_download(request: DownloadRequest):
    try:
        job_id = str(uuid.uuid4())
        await downloader.start_download(job_id, str(request.url), request.format_selector)
        return DownloadResponse(
            job_id=job_id,
            status="started",
            message="Download started",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to start download: {str(e)}")


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    job = downloader.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        speed=job.speed,
        eta=job.eta,
        filename=job.filename,
        filepath=job.filepath,
        error=job.error,
    )


@router.delete("/cancel/{job_id}")
async def cancel_download(job_id: str):
    if downloader.cancel_job(job_id):
        return {"status": "cancelled", "message": f"Job {job_id} cancelled"}
    raise HTTPException(status_code=404, detail="Job not found or already completed")


@router.get("/files", response_model=List[FileInfo])
async def list_files():
    files = []
    if DOWNLOADS_DIR.exists():
        for f in DOWNLOADS_DIR.iterdir():
            if f.is_file():
                stat = f.stat()
                files.append(
                    FileInfo(
                        filename=f.name,
                        filepath=str(f),
                        size=stat.st_size,
                        created_at=stat.st_ctime,
                    )
                )
    return files


@router.get("/download/{filename}")
async def download_file(filename: str):
    filepath = DOWNLOADS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        filepath,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.delete("/files/{filename}")
async def delete_file(filename: str):
    filepath = DOWNLOADS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    filepath.unlink()
    return {"status": "deleted", "filename": filename}


@router.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await ws_manager.connect(websocket, job_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, job_id)