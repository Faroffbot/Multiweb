class VideoDownloader {
    constructor() {
        this.apiUrl = '/api';
        this.ws = null;
        this.currentJobId = null;
        this.currentUrl = null;
        this.videoInfo = null;
        this.logs = [];
        
        this.init();
    }

    async init() {
        this.bindEvents();
        await this.loadFiles();
    }

    bindEvents() {
        const urlInput = document.getElementById('urlInput');
        const getInfoBtn = document.getElementById('getInfoBtn');
        const downloadBtn = document.getElementById('downloadBtn');

        urlInput.addEventListener('input', () => this.onUrlChange());
        urlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.getVideoInfo();
        });
        getInfoBtn.addEventListener('click', () => this.getVideoInfo());
        downloadBtn.addEventListener('click', () => this.startDownload());

        const refreshFilesBtn = document.getElementById('refreshFilesBtn');
        if (refreshFilesBtn) {
            refreshFilesBtn.addEventListener('click', () => this.loadFiles());
        }
    }

    onUrlChange() {
        const url = document.getElementById('urlInput').value.trim();
        const getInfoBtn = document.getElementById('getInfoBtn');
        
        if (url && this.isValidUrl(url)) {
            getInfoBtn.disabled = false;
        } else {
            getInfoBtn.disabled = true;
        }

        document.getElementById('videoPreview').classList.remove('active');
        document.getElementById('progressSection').classList.remove('active');
    }

    isValidUrl(string) {
        try {
            new URL(string);
            return true;
        } catch (_) {
            return false;
        }
    }

    async getVideoInfo() {
        const url = document.getElementById('urlInput').value.trim();
        const getInfoBtn = document.getElementById('getInfoBtn');
        const errorDiv = document.getElementById('errorMessage');
        
        this.hideError();
        getInfoBtn.disabled = true;
        getInfoBtn.innerHTML = '<span class="spinner"></span>Fetching...';

        try {
            const response = await fetch(`${this.apiUrl}/info`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Failed to fetch video info');
            }

            this.videoInfo = await response.json();
            this.displayVideoInfo(this.videoInfo);
        } catch (error) {
            this.showError(error.message);
        } finally {
            getInfoBtn.disabled = false;
            getInfoBtn.textContent = 'Get Video Info';
        }
    }

    displayVideoInfo(info) {
        document.getElementById('videoTitle').textContent = info.title;
        document.getElementById('videoThumbnail').src = info.thumbnail;
        document.getElementById('videoDuration').textContent = this.formatDuration(info.duration);
        document.getElementById('videoSize').textContent = this.formatSize(info.filesize);
        
        document.getElementById('videoPreview').classList.add('active');
    }

    async startDownload() {
        const url = document.getElementById('urlInput').value.trim();
        const formatSelector = document.getElementById('formatSelect').value;
        const downloadBtn = document.getElementById('downloadBtn');
        
        this.hideError();
        downloadBtn.disabled = true;
        downloadBtn.innerHTML = '<span class="spinner"></span>Starting...';

        try {
            const response = await fetch(`${this.apiUrl}/download`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    url,
                    format_selector: formatSelector 
                })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Failed to start download');
            }

            const result = await response.json();
            this.currentJobId = result.job_id;
            this.currentUrl = url;
            
            this.connectWebSocket(this.currentJobId);
            document.getElementById('progressSection').classList.add('active');
            this.updateProgressStatus('connecting', 'Connecting...');
            this.clearLogs();
            this.addLog('info', `Starting download for: ${url}`);
            
            downloadBtn.textContent = 'Download Started';
        } catch (error) {
            this.showError(error.message);
            downloadBtn.disabled = false;
            downloadBtn.textContent = 'Download';
        }
    }

    connectWebSocket(jobId) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/ws/${jobId}`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            this.addLog('info', 'WebSocket connected');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWsMessage(data);
        };
        
        this.ws.onerror = (error) => {
            this.addLog('error', 'WebSocket error occurred');
        };
        
        this.ws.onclose = () => {
            this.addLog('info', 'WebSocket disconnected');
        };
    }

    handleWsMessage(data) {
        switch (data.type) {
            case 'progress':
                this.updateProgress(data);
                break;
            case 'log':
                this.addLog('info', data.message);
                break;
            case 'complete':
                this.handleDownloadComplete(data);
                break;
            case 'error':
                this.addLog('error', data.error);
                this.updateProgressStatus('error', 'Download Failed');
                break;
        }
    }

    updateProgress(data) {
        const percent = data.progress || 0;
        
        document.getElementById('progressPercent').textContent = `${percent.toFixed(1)}%`;
        document.getElementById('progressBar').style.width = `${percent}%`;
        document.getElementById('progressSpeed').textContent = data.speed || '--';
        document.getElementById('progressTotal').textContent = data.total || '--';
        document.getElementById('progressEta').textContent = data.eta || '--';
        document.getElementById('progressFilename').textContent = data.filename || '--';
        
        if (data.log) {
            this.addLog('info', data.log);
        }
        
        this.updateProgressStatus('downloading', `Downloading: ${percent.toFixed(1)}%`);
    }

    handleDownloadComplete(data) {
        this.updateProgressStatus('success', 'Download Complete!');
        this.addLog('success', `File saved: ${data.filename}`);
        
        setTimeout(() => {
            this.loadFiles();
            this.resetDownload();
        }, 2000);
    }

    updateProgressStatus(status, message) {
        const statusEl = document.getElementById('progressStatus');
        statusEl.textContent = message;
        
        statusEl.className = 'progress-status';
        if (status === 'success') statusEl.classList.add('success');
        if (status === 'error') statusEl.classList.add('error');
    }

    clearLogs() {
        this.logs = [];
        document.getElementById('logConsole').innerHTML = '';
    }

    addLog(type, message) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${type}`;
        logEntry.textContent = `[${timestamp}] ${message}`;
        
        const console = document.getElementById('logConsole');
        console.appendChild(logEntry);
        console.scrollTop = console.scrollHeight;
        
        this.logs.push({ type, message, timestamp });
    }

    resetDownload() {
        const downloadBtn = document.getElementById('downloadBtn');
        downloadBtn.disabled = false;
        downloadBtn.textContent = 'Download';
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        this.currentJobId = null;
    }

    async loadFiles() {
        try {
            const response = await fetch(`${this.apiUrl}/files`);
            const files = await response.json();
            this.displayFiles(files);
        } catch (error) {
            console.error('Failed to load files:', error);
        }
    }

    displayFiles(files) {
        const container = document.getElementById('filesList');
        
        if (files.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                    No downloads yet. Start by pasting a URL above!
                </div>
            `;
            return;
        }

        container.innerHTML = files.map(file => `
            <div class="file-item" data-filename="${file.filename}">
                <div class="file-info">
                    <div class="file-name">${file.filename}</div>
                    <div class="file-size">${this.formatSize(file.size)}</div>
                </div>
                <div class="file-actions">
                    <button class="btn btn-sm btn-download" onclick="app.downloadFile('${file.filename}')">
                        Download
                    </button>
                    <button class="btn btn-sm btn-delete" onclick="app.deleteFile('${file.filename}')">
                        Delete
                    </button>
                </div>
            </div>
        `).join('');
    }

    downloadFile(filename) {
        window.location.href = `${this.apiUrl}/download/${filename}`;
    }

    async deleteFile(filename) {
        if (!confirm(`Delete "${filename}"?`)) return;
        
        try {
            const response = await fetch(`${this.apiUrl}/files/${filename}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                await this.loadFiles();
            }
        } catch (error) {
            console.error('Failed to delete file:', error);
        }
    }

    formatDuration(seconds) {
        if (!seconds) return '--';
        
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hrs > 0) {
            return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    formatSize(bytes) {
        if (!bytes || bytes === 0) return '--';
        
        const units = ['B', 'KB', 'MB', 'GB'];
        let unitIndex = 0;
        let size = bytes;
        
        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex++;
        }
        
        return `${size.toFixed(1)} ${units[unitIndex]}`;
    }

    showError(message) {
        const errorDiv = document.getElementById('errorMessage');
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
    }

    hideError() {
        document.getElementById('errorMessage').classList.add('hidden');
    }
}

const app = new VideoDownloader();