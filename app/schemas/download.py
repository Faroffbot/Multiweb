from typing import Optional
from pydantic import BaseModel, HttpUrl


class VideoInfoResponse(BaseModel):
    title: str
    thumbnail: str
    duration: int = 0
    filesize: Optional[int] = None
    url: str


class DownloadRequest(BaseModel):
    url: HttpUrl
    format_selector: Optional[str] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    audio_only: bool = False


class DownloadResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    speed: str
    eta: str
    filename: Optional[str] = None
    filepath: Optional[str] = None
    error: Optional[str] = None


class FileInfo(BaseModel):
    filename: str
    filepath: str
    size: int
    created_at: float