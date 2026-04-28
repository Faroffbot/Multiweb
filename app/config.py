import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
LOGS_DIR = BASE_DIR / "logs"

YTDLP_PATH = "yt-dlp"
ARIA2C_PATH = "/home/codespace/.local/bin/aria2c"

ARIA2C_CONNECTIONS = 16
ARIA2C_MIN_SPLIT = "50M"

MAX_CONCURRENT_DOWNLOADS = 3

DOWNLOAD_CHUNK_SIZE = 8192

DOWNLOAD_FORMATS = [
    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "best",
]

ALLOWED_URLPrefixes = [
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "dailymotion.com",
    "soundcloud.com",
    "twitter.com",
    "x.com",
]

os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)