import json
from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        self.active_connections[job_id].add(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str):
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def send_progress(self, job_id: str, data: dict):
        if job_id in self.active_connections:
            disconnected = set()
            for websocket in self.active_connections[job_id]:
                try:
                    await websocket.send_json(data)
                except Exception:
                    disconnected.add(websocket)
            for ws in disconnected:
                self.disconnect(ws, job_id)

    async def send_error(self, job_id: str, error: str):
        await self.send_progress(job_id, {
            "type": "error",
            "error": error
        })

    async def send_complete(self, job_id: str, filename: str, filepath: str):
        await self.send_progress(job_id, {
            "type": "complete",
            "filename": filename,
            "filepath": filepath
        })

    async def send_log(self, job_id: str, message: str):
        await self.send_progress(job_id, {
            "type": "log",
            "message": message
        })


ws_manager = ConnectionManager()