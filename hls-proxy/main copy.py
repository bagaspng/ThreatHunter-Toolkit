from fastapi import FastAPI, Response, Request, Query
from fastapi.responses import HTMLResponse
from curl_cffi import requests
import urllib.parse
import re
import time
from collections import deque

from config import STREAM_URL, REFERER

app = FastAPI(title="HLS Proxy")

# Store the last 30 proxy transactions for the dashboard log
proxy_logs = deque(maxlen=30)

def log_transaction(endpoint: str, status_code: int, url: str):
    parsed = urllib.parse.urlparse(url)
    filename = parsed.path.split("/")[-1] or parsed.path
    proxy_logs.append({
        "timestamp": time.strftime("%H:%M:%S"),
        "endpoint": endpoint,
        "status": status_code,
        "file": filename,
        "full_url": url
    })

def rewrite_playlist(content: str) -> str:
    """
    Rewrites the remote playlist so that segment and key URLs are proxied
    through our local FastAPI server using relative paths.
    """
    lines = content.splitlines()
    new_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            new_lines.append(line)
            continue
            
        # 1. Rewrite Decryption Keys: #EXT-X-KEY:METHOD=AES-128,URI="https://..."
        if stripped.startswith("#EXT-X-KEY:"):
            match = re.search(r'URI="([^"]+)"', stripped)
            if match:
                original_uri = match.group(1)
                # Proxy key URL through /key
                encoded_uri = f"/key?url={urllib.parse.quote(original_uri, safe='')}"
                new_line = stripped.replace(f'URI="{original_uri}"', f'URI="{encoded_uri}"')
                new_lines.append(new_line)
            else:
                new_lines.append(line)
                
        # 2. Rewrite Initialization Maps: #EXT-X-MAP:URI="https://..."
        elif stripped.startswith("#EXT-X-MAP:"):
            match = re.search(r'URI="([^"]+)"', stripped)
            if match:
                original_uri = match.group(1)
                # Proxy map URL through /segment
                encoded_uri = f"/segment?url={urllib.parse.quote(original_uri, safe='')}"
                new_line = stripped.replace(f'URI="{original_uri}"', f'URI="{encoded_uri}"')
                new_lines.append(new_line)
            else:
                new_lines.append(line)
                
        # 3. Rewrite Segment URLs: Lines not starting with '#' that contain absolute URLs
        elif not stripped.startswith("#"):
            if stripped.startswith("http://") or stripped.startswith("https://"):
                # Proxy segment URL through /segment
                encoded_url = f"/segment?url={urllib.parse.quote(stripped, safe='')}"
                new_lines.append(encoded_url)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    return "\n".join(new_lines)


@app.get("/")
def index():
    """Serves the premium HLS Video Player & Proxy Traffic Dashboard."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>HLS Proxy Player & Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
        <style>
            :root {
                --bg-primary: #0f172a;
                --bg-secondary: rgba(30, 41, 59, 0.7);
                --accent: #6366f1;
                --accent-hover: #4f46e5;
                --text-primary: #f8fafc;
                --text-secondary: #94a3b8;
                --success: #10b981;
                --error: #ef4444;
                --border: rgba(255, 255, 255, 0.08);
            }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }

            body {
                font-family: 'Plus Jakarta Sans', sans-serif;
                background: radial-gradient(circle at top left, #1e1b4b, #0f172a 60%);
                color: var(--text-primary);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                overflow-x: hidden;
            }

            header {
                padding: 1.5rem 2rem;
                border-bottom: 1px solid var(--border);
                backdrop-filter: blur(12px);
                background: rgba(15, 23, 42, 0.5);
                display: flex;
                justify-content: space-between;
                align-items: center;
                position: sticky;
                top: 0;
                z-index: 50;
            }

            .logo-container {
                display: flex;
                align-items: center;
                gap: 0.75rem;
            }

            .logo-icon {
                width: 2.2rem;
                height: 2.2rem;
                background: linear-gradient(135deg, var(--accent), #a855f7);
                border-radius: 0.5rem;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
            }

            .logo-text h1 {
                font-size: 1.25rem;
                font-weight: 700;
                letter-spacing: -0.025em;
            }

            .logo-text p {
                font-size: 0.75rem;
                color: var(--text-secondary);
            }

            .status-badge {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                background: rgba(16, 185, 129, 0.1);
                border: 1px solid rgba(16, 185, 129, 0.2);
                color: var(--success);
                padding: 0.35rem 0.75rem;
                border-radius: 9999px;
                font-size: 0.8rem;
                font-weight: 600;
            }

            .status-dot {
                width: 8px;
                height: 8px;
                background-color: var(--success);
                border-radius: 50%;
                animation: pulse 1.5s infinite;
            }

            @keyframes pulse {
                0% { opacity: 0.4; transform: scale(1); }
                50% { opacity: 1; transform: scale(1.2); }
                100% { opacity: 0.4; transform: scale(1); }
            }

            main {
                flex: 1;
                display: grid;
                grid-template-columns: 1.2fr 0.8fr;
                gap: 2rem;
                padding: 2rem;
                max-width: 1600px;
                width: 100%;
                margin: 0 auto;
            }

            @media (max-width: 1024px) {
                main {
                    grid-template-columns: 1fr;
                }
            }

            .card {
                background: var(--bg-secondary);
                border: 1px solid var(--border);
                border-radius: 1rem;
                backdrop-filter: blur(16px);
                overflow: hidden;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
                display: flex;
                flex-direction: column;
            }

            .card-header {
                padding: 1.25rem 1.5rem;
                border-bottom: 1px solid var(--border);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .card-title {
                font-size: 1.1rem;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }

            .player-container {
                position: relative;
                width: 100%;
                aspect-ratio: 16/9;
                background: #000;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            video {
                width: 100%;
                height: 100%;
                display: block;
            }

            .info-panel {
                padding: 1.5rem;
                display: flex;
                flex-direction: column;
                gap: 1.25rem;
            }

            .info-group {
                display: flex;
                flex-direction: column;
                gap: 0.35rem;
            }

            .info-label {
                font-size: 0.75rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: var(--text-secondary);
                font-weight: 600;
            }

            .info-value {
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.85rem;
                background: rgba(15, 23, 42, 0.4);
                padding: 0.6rem 0.8rem;
                border-radius: 0.5rem;
                border: 1px solid var(--border);
                word-break: break-all;
            }

            /* Log Panel Styling */
            .logs-panel {
                max-height: 700px;
                display: flex;
                flex-direction: column;
            }

            .logs-container {
                flex: 1;
                overflow-y: auto;
                padding: 1rem;
                display: flex;
                flex-direction: column;
                gap: 0.75rem;
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.8rem;
                min-height: 400px;
            }

            .log-entry {
                display: flex;
                flex-direction: column;
                gap: 0.25rem;
                padding: 0.65rem 0.85rem;
                border-radius: 0.5rem;
                background: rgba(15, 23, 42, 0.3);
                border-left: 3px solid var(--accent);
                transition: transform 0.2s ease, background 0.2s ease;
            }

            .log-entry:hover {
                transform: translateX(2px);
                background: rgba(15, 23, 42, 0.5);
            }

            .log-entry.get-playlist { border-left-color: #818cf8; }
            .log-entry.get-segment { border-left-color: #34d399; }
            .log-entry.get-key { border-left-color: #fbbf24; }

            .log-meta {
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 0.75rem;
            }

            .log-time {
                color: var(--text-secondary);
            }

            .log-badge {
                padding: 0.15rem 0.4rem;
                border-radius: 0.25rem;
                font-weight: 600;
                font-size: 0.7rem;
            }

            .log-badge.success {
                background: rgba(16, 185, 129, 0.15);
                color: var(--success);
            }

            .log-badge.error {
                background: rgba(239, 68, 68, 0.15);
                color: var(--error);
            }

            .log-endpoint {
                font-weight: 600;
                color: var(--text-primary);
            }

            .log-file {
                color: var(--text-secondary);
                word-break: break-all;
                margin-top: 0.1rem;
            }

            /* Custom Scrollbar */
            ::-webkit-scrollbar {
                width: 6px;
            }
            ::-webkit-scrollbar-track {
                background: transparent;
            }
            ::-webkit-scrollbar-thumb {
                background: rgba(255, 255, 255, 0.15);
                border-radius: 3px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: rgba(255, 255, 255, 0.3);
            }

            .empty-logs {
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100%;
                color: var(--text-secondary);
                font-style: italic;
            }
        </style>
    </head>
    <body>
        <header>
            <div class="logo-container">
                <div class="logo-icon">H</div>
                <div class="logo-text">
                    <h1>HLS Proxy</h1>
                    <p>Milestone 6: Stream Proxy & Player Dashboard</p>
                </div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>Bypass Active (curl_cffi)</span>
            </div>
        </header>

        <main>
            <!-- Left Side: Player Card -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--accent);"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                        HLS.js Live Player
                    </div>
                </div>
                <div class="player-container">
                    <video id="video" controls autoplay muted></video>
                </div>
                <div class="info-panel">
                    <div class="info-group">
                        <div class="info-label">Active Proxy Playlist Endpoint</div>
                        <div class="info-value" id="local-playlist-url">Loading...</div>
                    </div>
                    <div class="info-group">
                        <div class="info-label">Remote Stream URL (Source)</div>
                        <div class="info-value">""" + STREAM_URL + """</div>
                    </div>
                    <div class="info-group">
                        <div class="info-label">Required Referer Header</div>
                        <div class="info-value">""" + REFERER + """</div>
                    </div>
                </div>
            </div>

            <!-- Right Side: Logs Dashboard -->
            <div class="card logs-panel">
                <div class="card-header">
                    <div class="card-title">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--accent);"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>
                        Proxy Live traffic
                    </div>
                </div>
                <div class="logs-container" id="logs-container">
                    <div class="empty-logs">Waiting for requests...</div>
                </div>
            </div>
        </main>

        <script>
            // Set playlist url text
            const playlistUrl = window.location.origin + '/playlist';
            document.getElementById('local-playlist-url').innerText = playlistUrl;

            // Initialize Player
            const video = document.getElementById('video');
            if (Hls.isSupported()) {
                const hls = new Hls({
                    maxMaxBufferLength: 30,
                    enableWorker: true
                });
                hls.loadSource(playlistUrl);
                hls.attachMedia(video);
                hls.on(Hls.Events.MANIFEST_PARSED, function() {
                    video.play();
                });
            } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                // native support (Safari / iOS)
                video.src = playlistUrl;
                video.addEventListener('canplay', function() {
                    video.play();
                });
            }

            // Poll log data
            const logsContainer = document.getElementById('logs-container');
            let lastLogTime = '';

            async function updateLogs() {
                try {
                    const response = await fetch('/api/logs');
                    const logs = await response.json();
                    
                    if (logs.length === 0) {
                        logsContainer.innerHTML = '<div class="empty-logs">Waiting for requests...</div>';
                        return;
                    }

                    logsContainer.innerHTML = logs.reverse().map(log => {
                        let endpointClass = '';
                        if (log.endpoint.includes('/playlist')) endpointClass = 'get-playlist';
                        else if (log.endpoint.includes('/segment')) endpointClass = 'get-segment';
                        else if (log.endpoint.includes('/key')) endpointClass = 'get-key';

                        const badgeClass = log.status === 200 ? 'success' : 'error';

                        return `
                            <div class="log-entry ${endpointClass}">
                                <div class="log-meta">
                                    <span class="log-endpoint">${log.endpoint}</span>
                                    <span class="log-badge ${badgeClass}">${log.status}</span>
                                </div>
                                <div class="log-file">${log.file}</div>
                                <div class="log-time">${log.timestamp}</div>
                            </div>
                        `;
                    }).join('');
                } catch (err) {
                    console.error("Failed to fetch logs:", err);
                }
            }

            // Update immediately and then every 1 second
            updateLogs();
            setInterval(updateLogs, 1000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/playlist")
def playlist():
    """
    Milestone 2 & 3:
    Fetches the remote playlist (.m3u8), rewrites all key/segment URIs
    to go through the proxy, and returns the modified playlist.
    """
    headers = {
        "Referer": REFERER
    }

    try:
        response = requests.get(
            STREAM_URL,
            headers=headers,
            impersonate="chrome"
        )
        
        log_transaction("/playlist", response.status_code, STREAM_URL)
        
        if response.status_code != 200:
            return Response(
                content=f"Error {response.status_code}: {response.text[:200]}",
                status_code=response.status_code
            )

        # Milestone 3: Rewrite remote URL paths to go through local endpoints
        rewritten_content = rewrite_playlist(response.text)

        return Response(
            content=rewritten_content,
            media_type="application/vnd.apple.mpegurl"
        )
    except Exception as e:
        log_transaction("/playlist", 500, STREAM_URL)
        return Response(content=str(e), status_code=500)


@app.get("/segment")
def proxy_segment(url: str = Query(..., description="The absolute URL of the segment to fetch")):
    """
    Milestone 4:
    Proxies HLS segment requests (.jpg / .ts / etc.) using curl_cffi with 
    the necessary Referer header and Chrome impersonation.
    """
    headers = {
        "Referer": REFERER
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            impersonate="chrome"
        )
        
        log_transaction("/segment", response.status_code, url)
        
        if response.status_code != 200:
            return Response(
                content=response.content,
                status_code=response.status_code
            )

        # Forward the content type returned from the source server, or default to MPEG-TS
        content_type = response.headers.get("content-type", "video/MP2T")

        return Response(
            content=response.content,
            media_type=content_type
        )
    except Exception as e:
        log_transaction("/segment", 500, url)
        return Response(content=str(e), status_code=500)


@app.get("/key")
def proxy_key(url: str = Query(..., description="The absolute URL of the decryption key to fetch")):
    """
    Milestone 5:
    Proxies DRM decryption key requests (.key) using curl_cffi.
    """
    headers = {
        "Referer": REFERER
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            impersonate="chrome"
        )
        
        log_transaction("/key", response.status_code, url)
        
        if response.status_code != 200:
            return Response(
                content=response.content,
                status_code=response.status_code
            )

        return Response(
            content=response.content,
            media_type="application/octet-stream"
        )
    except Exception as e:
        log_transaction("/key", 500, url)
        return Response(content=str(e), status_code=500)


@app.get("/api/logs")
def get_logs():
    """Returns the list of proxy transaction logs for the dashboard."""
    return list(proxy_logs)