import asyncio
import json
import logging
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from yt_dlp.utils import std_headers

from app.config import (
    DOWNLOADS_DIR,
    ARIA2C_CONNECTIONS,
    ARIA2C_MIN_SPLIT,
    YTDLP_PATH,
    ARIA2C_PATH,
)
from app.core.websocket import ws_manager


class VideoInfo:
    def __init__(self, title: str, thumbnail: str, duration: int, filesize: int, url: str):
        self.title = title
        self.thumbnail = thumbnail
        self.duration = duration
        self.filesize = filesize
        self.url = url

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "thumbnail": self.thumbnail,
            "duration": self.duration,
            "filesize": self.filesize,
            "url": self.url,
        }


class DownloadJob:
    def __init__(
        self,
        job_id: str,
        url: str,
        format_selector: str = "best[ext=mp4]/best",
        audio_only: bool = False,
    ):
        self.job_id = job_id
        self.url = url
        self.format_selector = format_selector
        self.audio_only = audio_only
        self.status = "pending"
        self.progress = 0.0
        self.speed = ""
        self.eta = ""
        self.filename = ""
        self.filepath = ""
        self.error: Optional[str] = None
        self.process: Optional[asyncio.subprocess.Process] = None
        self._progress_callbacks = []

    def on_progress(self, callback):
        self._progress_callbacks.append(callback)

    def update_progress(self, progress: float, speed: str, eta: str, filename: str):
        self.progress = progress
        self.speed = speed
        self.eta = eta
        self.filename = filename
        for cb in self._progress_callbacks:
            cb(self)


class Downloader:
    def __init__(self):
        self.jobs: Dict[str, DownloadJob] = {}
        self._executor = ThreadPoolExecutor(max_workers=2)

    def _format_size(self, size):
        if not size: return "0B"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024: return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    async def get_video_info(self, url: str) -> VideoInfo:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Unknown")
            thumbnail = info.get("thumbnail", info.get("thumbnails", [{}])[0].get("url", ""))
            duration = info.get("duration") or 0
            filesize = info.get("filesize") or info.get("filesize_approx") or 0

            return VideoInfo(
                title=title,
                thumbnail=thumbnail,
                duration=int(duration) if duration else 0,
                filesize=int(filesize) if filesize else 0,
                url=url,
            )

    async def start_download(
        self,
        job_id: str,
        url: str,
        format_selector: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    ) -> str:
        job = DownloadJob(job_id, url, format_selector)
        self.jobs[job_id] = job

        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self._run_download_sync, job)

        return job_id

    def _run_download_sync(self, job: DownloadJob):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(ws_manager.send_log(job.job_id, f"Starting download for: {job.url}"))

            output_template = str(DOWNLOADS_DIR / f"%(title)s.%(ext)s")

            def progress_hook(d):
                status = d.get("status", "")
                
                if status == "downloading":
                    progress_str = d.get("progress", "0")
                    try:
                        progress = float(progress_str.replace("%", ""))
                    except (ValueError, AttributeError):
                        progress = 0.0

                    speed = d.get("speed", "")
                    eta = d.get("eta", "")
                    filename = d.get("filename", "")
                    total_bytes = d.get("total_bytes", 0)
                    downloaded_bytes = d.get("downloaded_bytes", 0)
                    
                    prev_progress = job.progress
                    job.update_progress(progress, speed, eta, filename)
                    
                    should_log = (progress - prev_progress >= 2) or progress >= 100 or progress == 0
                    if should_log:
                        total_str = f"{downloaded_bytes}/{self._format_size(total_bytes)}" if total_bytes else "?.?"
                        log_msg = f"[{progress:.1f}%] {total_str} @ {speed} ETA:{eta}"
                        try:
                            loop = asyncio.get_event_loop()
                            loop.run_until_complete(
                                ws_manager.send_progress(
                                    job.job_id,
                                    {
                                        "type": "progress",
                                        "progress": progress,
                                        "speed": speed,
                                        "eta": eta,
                                        "filename": filename,
                                        "total": total_str,
                                        "log": log_msg,
                                    },
                                )
                            )
                        except Exception:
                            pass
                elif status == "finished":
                    job.update_progress(100.0, "", "", d.get("filename", ""))

            ydl_opts = {
                "format": job.format_selector,
                "outtmpl": output_template,
                "progress_hooks": [progress_hook],
                "quiet": True,
                "no_warnings": True,
                "http_chunk_size": 10_000_000,
            }

            if ARIA2C_PATH:
                ydl_opts["downloader"] = "aria2c"
                ydl_opts["downloader_args"] = [
                    f"max_connections={ARIA2C_CONNECTIONS}",
                    f"min_split_size={ARIA2C_MIN_SPLIT}",
                    f"split={ARIA2C_CONNECTIONS}"
                ]
                ws_log_msg = f"Using aria2c with {ARIA2C_CONNECTIONS} parallel connections"
            else:
                ydl_opts["http_dynamic_range"] = True
                ws_log_msg = f"Using default downloader with chunked HTTP"

            loop.run_until_complete(ws_manager.send_log(job.job_id, ws_log_msg))

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(job.url, download=True)
                job.filename = ydl.prepare_filename(info)
                job.filepath = job.filename

            job.status = "completed"
            loop.run_until_complete(ws_manager.send_complete(job.job_id, job.filename, job.filepath))
            loop.run_until_complete(ws_manager.send_log(job.job_id, f"Download complete: {job.filename}"))

        except Exception as e:
            job.status = "error"
            job.error = str(e)
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(ws_manager.send_error(job.job_id, str(e)))
                loop.run_until_complete(ws_manager.send_log(job.job_id, f"Error: {str(e)}"))
            except Exception:
                pass

    def get_job(self, job_id: str) -> Optional[DownloadJob]:
        return self.jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job and job.process:
            job.process.terminate()
            job.status = "cancelled"
            return True
        return False


downloader = Downloader()