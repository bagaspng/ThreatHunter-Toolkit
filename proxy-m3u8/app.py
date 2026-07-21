import sys
import ssl
import urllib.request
import urllib.error
from urllib.parse import quote
from flask import Flask, request, Response
from curl_cffi import requests


app = Flask(__name__)

# Common lowercase headers to bypass Juicy Codes / Juicy Nginx WAF checks
COMMON_HEADERS = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "origin": "https://199.87.210.226",
    "priority": "u=1, i",
    "referer": "https://199.87.210.226/",
    "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
}

@app.route("/")
def index():
    # Diagnostic HLS Proxy Player with premium Dark Mode UI
    html = """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Diagnostic HLS Proxy Player</title>
        <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-main: #0b0c10;
                --bg-card: rgba(21, 23, 30, 0.8);
                --border-color: rgba(255, 255, 255, 0.08);
                --accent-blue: #38bdf8;
                --accent-green: #10b981;
                --accent-yellow: #f59e0b;
                --accent-red: #ef4444;
                --text-main: #f1f5f9;
                --text-muted: #94a3b8;
            }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }

            body {
                font-family: 'Inter', sans-serif;
                background-color: var(--bg-main);
                color: var(--text-main);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                padding: 12px; /* Small bezel padding */
            }

            .header {
                max-width: 1400px;
                width: 100%;
                margin: 0 auto 12px auto;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }

            .logo {
                display: flex;
                align-items: center;
                gap: 12px;
                font-size: 20px;
                font-weight: 700;
                color: #fff;
                background: linear-gradient(135deg, var(--accent-blue), #818cf8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }

            .logo-dot {
                width: 10px;
                height: 10px;
                background-color: var(--accent-blue);
                border-radius: 50%;
                box-shadow: 0 0 10px var(--accent-blue);
                animation: pulse 1.5s infinite alternate;
            }

            @keyframes pulse {
                0% { transform: scale(0.8); opacity: 0.5; }
                100% { transform: scale(1.2); opacity: 1; }
            }

            .container {
                max-width: 1400px;
                width: 100%;
                margin: 0 auto;
                display: flex;
                flex-direction: column;
                gap: 16px;
                flex-grow: 1;
            }

            .card {
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 16px; /* Small bezel padding inside card */
                backdrop-filter: blur(12px);
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
                display: flex;
                flex-direction: column;
            }

            .input-section {
                margin-bottom: 0px;
            }

            .form-group {
                display: flex;
                gap: 12px;
                margin-top: 10px;
            }

            input[type="text"] {
                flex-grow: 1;
                padding: 14px 16px;
                background: rgba(0, 0, 0, 0.4);
                border: 1px solid var(--border-color);
                border-radius: 10px;
                color: #fff;
                font-family: inherit;
                font-size: 14px;
                outline: none;
                transition: border-color 0.25s, box-shadow 0.25s;
            }

            input[type="text"]:focus {
                border-color: var(--accent-blue);
                box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.15);
            }

            button.btn-play {
                padding: 14px 28px;
                background: linear-gradient(135deg, var(--accent-blue), #4f46e5);
                border: none;
                border-radius: 10px;
                color: #fff;
                font-weight: 600;
                font-family: inherit;
                cursor: pointer;
                transition: transform 0.15s, filter 0.2s;
                box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
            }

            button.btn-play:hover {
                filter: brightness(1.1);
            }

            button.btn-play:active {
                transform: scale(0.97);
            }

            /* Video Section */
            .player-card {
                position: relative;
                aspect-ratio: 16/9;
                background: #000;
                border-radius: 12px;
                overflow: hidden;
                border: 1px solid var(--border-color);
                width: 100%;
            }

            video {
                width: 100%;
                height: 100%;
                display: block;
            }

            /* Loading Overlay */
            .loader-overlay {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.6);
                display: none;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                z-index: 10;
                gap: 16px;
                pointer-events: none; /* Clicks pass through to the video elements */
            }

            .spinner {
                width: 48px;
                height: 48px;
                border: 4px solid rgba(56, 189, 248, 0.1);
                border-top-color: var(--accent-blue);
                border-radius: 50%;
                animation: spin 1s infinite linear;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .loader-text {
                font-size: 14px;
                font-weight: 500;
                color: var(--accent-blue);
            }

            /* Console Section */
            .console-card {
                max-height: 380px;
                height: auto;
            }

            .console-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 12px;
                padding-bottom: 8px;
                border-bottom: 1px solid var(--border-color);
            }

            .console-title {
                font-size: 14px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: var(--text-muted);
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .console-controls {
                display: flex;
                align-items: center;
                gap: 12px;
                font-size: 12px;
                color: var(--text-muted);
            }

            .console-controls input {
                cursor: pointer;
            }

            .console-btn-clear {
                background: transparent;
                border: none;
                color: var(--accent-red);
                cursor: pointer;
                font-weight: 600;
                font-family: inherit;
                font-size: 12px;
            }

            .console-btn-clear:hover {
                text-decoration: underline;
            }

            .console-log {
                background: #050608;
                border: 1px solid var(--border-color);
                border-radius: 10px;
                padding: 14px;
                flex-grow: 1;
                overflow-y: auto;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                line-height: 1.6;
                color: #e2e8f0;
                height: 220px; /* Reduced height for clean layout */
            }

            .log-line {
                margin-bottom: 8px;
                word-break: break-all;
                border-left: 2px solid transparent;
                padding-left: 8px;
            }

            .log-info { border-left-color: var(--accent-blue); }
            .log-success { border-left-color: var(--accent-green); }
            .log-warn { border-left-color: var(--accent-yellow); }
            .log-error { border-left-color: var(--accent-red); }

            .url-text {
                color: #f472b6;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo">
                <div class="logo-dot"></div>
                Proxy Film 
            </div>
            
        </div>

        <div class="container">
            <!-- Form Input -->
            <div class="card input-section">
                <h3 style="font-size: 15px; font-weight: 600;">Masukkan URL Video</h3>
                <div class="form-group">
                    <input type="text" id="urlInput" placeholder="Masukkan URL M3U8 Asli disini (Contoh: https://datura.groovy.monster/stream/...m3u8)" value="https://datura.groovy.monster/stream/BQyvMGplZmHmAQMyBQN5MTHjBJIvAmZ3AwV5MQR4AmMxLGL4LwIwMGLjZJAwZJVmA2WwLzAvA2Z4ZJSzAGIxMP50ARqbAJMVqyqiAyOcrSNjZII3FRcaYaHlAyW2rIp4GSyxEwx1DGyuAx9ZHzguGHkIMaqbMycVIGAJIP0jAmMlqmOKGJj3ZwZgDGZ0MwI3G21LZxD3nJ4/AJL0MTLkLmAzLzLlZTMxZmpkZQN4MGp2LJWyA2LjZGVjA2AyZTVlMQHjZmIzZzZ4BTHkBGMxMJL1LzDlMJL4Zv40rTWsFT1DGaMCDwSfqSyyBT9TImOOYwEmLyugAKucqRgiJGExGyOnnUO4n0IEIRciqRW1DHqkGTIIG2cxASIkJTyzBGqjZxEBIyHkAJ1zGRb4Z1qwrKD.m3u8">
                    <button class="btn-play" onclick="loadStream()">Play</button>
                </div>
            </div>

            <!-- Media Player Card -->
            <div class="card">
                <h3 style="font-size: 15px; font-weight: 600; margin-bottom: 12px;"> Media Player</h3>
                <div class="player-card">
                    <div class="loader-overlay" id="loader">
                        <div class="spinner"></div>
                        <div class="loader-text" id="loader-text">Loading stream...</div>
                    </div>
                    <video id="video" controls autoplay></video>
                </div>
            </div>

            <!-- Diagnostic Console Card below player -->
            <div class="card console-card">
                <div class="console-header">
                    <div class="console-title">
                        <span style="display:inline-block; width:8px; height:8px; background-color: var(--accent-blue); border-radius:50%"></span>
                        Diagnostic Logs
                    </div>
                    <div class="console-controls">
                        <label><input type="checkbox" id="auto-scroll" checked> Auto Scroll</label>
                        <button class="console-btn-clear" onclick="clearLogs()">Clear</button>
                    </div>
                </div>
                <div class="console-log" id="log-console">
                    <div style="color: var(--text-muted)">Console initialized. Paste stream URL and click "Play & Diagnose".</div>
                </div>
            </div>
        </div>

        <script>
            var video = document.getElementById('video');
            var loader = document.getElementById('loader');
            var loaderText = document.getElementById('loader-text');
            var hls = null;

            function showLoader(show, text = 'Loading stream...') {
                loader.style.display = show ? 'flex' : 'none';
                loaderText.textContent = text;
            }

            // Bind video element native events for accurate buffering/seeking feedback
            video.addEventListener('waiting', function() {
                showLoader(true, 'Buffering...');
            });
            video.addEventListener('playing', function() {
                showLoader(false);
            });
            video.addEventListener('seeking', function() {
                showLoader(true, 'Seeking...');
            });
            video.addEventListener('seeked', function() {
                showLoader(false);
            });
            video.addEventListener('loadstart', function() {
                showLoader(true, 'Initializing stream...');
            });
            video.addEventListener('loadedmetadata', function() {
                showLoader(false);
            });

            function log(message, type = 'info') {
                const consoleEl = document.getElementById('log-console');
                const time = new Date().toLocaleTimeString();
                const div = document.createElement('div');
                div.className = `log-line log-${type}`;
                
                let badgeColor = '#64748b';
                if (type === 'success') badgeColor = '#10b981';
                if (type === 'error') badgeColor = '#ef4444';
                if (type === 'warn') badgeColor = '#f59e0b';
                if (type === 'info') badgeColor = '#38bdf8';
                
                div.innerHTML = `<span style="color: #475569">[${time}]</span> <span style="color: ${badgeColor}; font-weight: 600;">[${type.toUpperCase()}]</span> ${message}`;
                consoleEl.appendChild(div);
                
                if (document.getElementById('auto-scroll').checked) {
                    consoleEl.scrollTop = consoleEl.scrollHeight;
                }
            }

            function clearLogs() {
                document.getElementById('log-console').innerHTML = '<div style="color: var(--text-muted)">Console cleared.</div>';
            }

            function loadStream() {
                var rawUrl = document.getElementById('urlInput').value.trim();
                if (!rawUrl) {
                    log('Error: URL kosong!', 'error');
                    return;
                }

                log('Memulai rantai pemutaran video...', 'info');

                // Deteksi otomatis format stream (HLS .m3u8 vs Direct Stream)
                var isHls = rawUrl.toLowerCase().includes('.m3u8');

                if (isHls) {
                    log('Tipe terdeteksi: HLS Playlist (.m3u8)', 'info');
                    var proxyUrl = '/api/v1/hls/master?url=' + encodeURIComponent(rawUrl);
                    log(`Mengubah URL asli ke Proxy Master HLS: <span class="url-text">${proxyUrl}</span>`, 'info');
                    
                    if (hls) {
                        log('Membersihkan instansi HLS sebelumnya.', 'info');
                        hls.destroy();
                        hls = null;
                    }
                    
                    showLoader(true, 'Fetching master playlist...');

                    if (Hls.isSupported()) {
                        hls = new Hls({
                            maxBufferLength: 30,
                            maxMaxBufferLength: 600,
                            xhrSetup: function(xhr, url) {
                                if (url.includes('/api/v1/hls/master')) {
                                    log(`[NETWORK] Menghubungi Master Proxy...`, 'info');
                                } else if (url.includes('/api/v1/hls/variant')) {
                                    log(`[NETWORK] Menghubungi Variant Proxy...`, 'info');
                                } else if (url.includes('/api/v1/hls/segment')) {
                                    log(`[NETWORK] Menghubungi Segment Proxy...`, 'info');
                                }
                            }
                        });

                        hls.on(Hls.Events.MANIFEST_LOADING, function(event, data) {
                            log(`HLS manifest loading dari: <span class="url-text">${data.url}</span>`, 'info');
                            showLoader(true, 'Loading manifest...');
                        });

                        hls.on(Hls.Events.MANIFEST_PARSED, function(event, data) {
                            log(`Master playlist parsed sukses! Menemukan ${data.levels.length} tingkat resolusi.`, 'success');
                        });

                        hls.on(Hls.Events.LEVEL_LOADING, function(event, data) {
                            log(`Mulai memuat playlist variant level ${data.level} (Resolusi target)...`, 'info');
                            showLoader(true, 'Loading variant playlist...');
                        });

                        hls.on(Hls.Events.LEVEL_LOADED, function(event, data) {
                            log(`Variant playlist level ${data.level} sukses dimuat! Durasi video: ${data.details.totalduration.toFixed(2)} detik.`, 'success');
                            showLoader(false);
                        });

                        hls.on(Hls.Events.FRAG_LOADING, function(event, data) {
                            log(`Mengunduh segmen video #${data.frag.sn} (Durasi segmen: ${data.frag.duration.toFixed(2)}s)...`, 'info');
                        });

                        hls.on(Hls.Events.FRAG_LOADED, function(event, data) {
                            const loadTimeMs = (data.stats.loading.end - data.stats.loading.start).toFixed(0);
                            const fileSizeMb = (data.stats.total / 1024 / 1024).toFixed(2);
                            const speedMbps = ((data.stats.total / 1024 / 1024) / (data.stats.loading.end - data.stats.loading.start) * 1000).toFixed(2);
                            log(`Segmen #${data.frag.sn} sukses dimuat! Ukuran: ${fileSizeMb} MB | Waktu download: ${loadTimeMs}ms (${speedMbps} Mbps)`, 'success');
                        });

                        hls.on(Hls.Events.ERROR, function(event, data) {
                            let errorMsg = `HLS Error: ${data.details} (Tipe: ${data.type})`;
                            if (data.response) {
                                errorMsg += ` | HTTP Status: ${data.response.code}`;
                                if (data.response.code === 403) {
                                    errorMsg += ' -> Kemungkinan WAF memblokir karena masalah Referer atau URL Token Kedaluwarsa!';
                                } else if (data.response.code === 0) {
                                    errorMsg += ' -> Kemungkinan timeout atau CORS error pada proxy!';
                                }
                            }
                            log(errorMsg, data.fatal ? 'error' : 'warn');

                            if (data.fatal) {
                                showLoader(false);
                                log('Fatal error! Mencoba memulihkan...', 'warn');
                                if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
                                    log('Network error fatal, memuat ulang fragment...', 'warn');
                                    hls.startLoad();
                                } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
                                    log('Media error fatal, memulihkan dekoder...', 'warn');
                                    hls.recoverMediaError();
                                } else {
                                    log('Fatal error tidak dapat dipulihkan, pemutaran dihentikan.', 'error');
                                    hls.destroy();
                                    hls = null;
                                }
                            }
                        });

                        hls.loadSource(proxyUrl);
                        hls.attachMedia(video);

                    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                        log('Hls.js tidak didukung pada browser ini, menggunakan pemutar bawaan sistem (Safari/iOS).', 'warn');
                        video.src = proxyUrl;
                    } else {
                        log('Fatal: Browser Anda tidak mendukung pemutaran HLS!', 'error');
                        showLoader(false);
                    }
                } else {
                    log('Tipe terdeteksi: Direct Video Stream (MP4/MKV/Raw)', 'info');
                    if (hls) {
                        log('Membersihkan instansi HLS untuk mode Direct Stream.', 'info');
                        hls.destroy();
                        hls = null;
                    }
                    
                    var directProxyUrl = '/api/v1/video/stream?url=' + encodeURIComponent(rawUrl);
                    log(`Mengubah URL asli ke Proxy Direct Stream: <span class="url-text">${directProxyUrl}</span>`, 'info');
                    
                    showLoader(true, 'Initializing direct stream...');
                    video.src = directProxyUrl;
                    video.play().catch(function(err) {
                        log('Auto-play blocked or failed: ' + err.message, 'warn');
                    });
                }
            }

            loadStream();
        </script>
    </body>
    </html>
    """
    return html

@app.route("/api/v1/hls/master")
def hls_master():
    url = request.args.get("url")
    referer = request.args.get("referer") or request.args.get("Referer")
    
    if not url:
        return "Missing url", 400

    headers = dict(COMMON_HEADERS)
    
    # Auto-detect referer if not explicitly passed
    if referer:
        headers["referer"] = referer
        headers["origin"] = referer.rstrip("/")
    elif "kwik.cx" in url:
        headers["referer"] = "https://kwik.cx/"
        headers["origin"] = "https://kwik.cx"

    r = requests.get(
        url,
        headers=headers,
        timeout=30,
        verify=False,
        impersonate="chrome",
    )
    playlist = r.text
    host = request.host_url.rstrip("/")
    new_lines = []

    for line in playlist.splitlines():
        if line.startswith("http") and line.endswith(".m3u8"):
            ref_param = f"&referer={quote(referer)}" if referer else ""
            proxy = f"{host}/api/v1/hls/variant?url={quote(line, safe='')}{ref_param}"
            new_lines.append(proxy)
        else:
            new_lines.append(line)

    return Response("\n".join(new_lines), mimetype="application/vnd.apple.mpegurl")

@app.route("/api/v1/hls/variant")
def hls_variant():
    url = request.args.get("url")
    referer = request.args.get("referer") or request.args.get("Referer")
    
    if not url:
        return "Missing url", 400

    headers = dict(COMMON_HEADERS)
    if referer:
        headers["referer"] = referer
        headers["origin"] = referer.rstrip("/")
    elif "kwik.cx" in url:
        headers["referer"] = "https://kwik.cx/"
        headers["origin"] = "https://kwik.cx"

    r = requests.get(
        url,
        headers=headers,
        timeout=30,
        verify=False,
        impersonate="chrome",
    )
    playlist = r.text
    host = request.host_url.rstrip("/")
    output = []

    for line in playlist.splitlines():
        if line.startswith("#"):
            output.append(line)
            continue
        if not line.strip():
            output.append(line)
            continue
        ref_param = f"&referer={quote(referer)}" if referer else ""
        proxy = f"{host}/api/v1/hls/segment?url={quote(line, safe='')}{ref_param}"
        output.append(proxy)

    return Response("\n".join(output), mimetype="application/vnd.apple.mpegurl")

@app.route("/api/v1/hls/segment")
def hls_segment():
    url = request.args.get("url")
    referer = request.args.get("referer") or request.args.get("Referer")
    
    if not url:
        return "Missing url", 400

    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    }
    
    if referer:
        headers["referer"] = referer
        headers["origin"] = referer.rstrip("/")
    elif "kwik.cx" in url:
        headers["referer"] = "https://kwik.cx/"
        headers["origin"] = "https://kwik.cx"
    else:
        headers["referer"] = "https://199.87.210.226/"
        headers["origin"] = "https://199.87.210.226"

    client_range = request.headers.get("Range")
    if client_range:
        headers["range"] = client_range
        headers["accept-encoding"] = "identity"

    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        response_stream = urllib.request.urlopen(req, context=ctx, timeout=30)
        status_code = response_stream.status
        
        resp_headers = {}
        for k, v in response_stream.getheaders():
            kl = k.lower()
            if kl in ["content-type", "content-length", "accept-ranges", "content-range"]:
                resp_headers[k] = v

        def generate():
            try:
                while True:
                    chunk = response_stream.read(65536)
                    if not chunk:
                        break
                    yield chunk
            finally:
                response_stream.close()

        return Response(
            generate(),
            status=status_code,
            headers=resp_headers
        )
    except urllib.error.HTTPError as e:
        return f"Upstream HTTP Error: {e.code}", e.code
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

@app.route("/api/v1/video/stream")
def video_stream():
    url = request.args.get("url")
    referer = request.args.get("referer") or request.args.get("Referer")
    
    if not url:
        return "Missing url", 400

    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    }

    if referer:
        headers["referer"] = referer
        headers["origin"] = referer.rstrip("/")
    else:
        # Smart detection fallback for referer based on target domain
        if "daisy.groovy.monster" in url:
            headers["referer"] = "https://178.211.139.171/"
            headers["origin"] = "https://178.211.139.171"
        elif "datura.groovy.monster" in url:
            headers["referer"] = "https://199.87.210.226/"
            headers["origin"] = "https://199.87.210.226"
        else:
            headers["referer"] = "https://199.87.210.226/"
            headers["origin"] = "https://199.87.210.226"

    client_range = request.headers.get("Range")
    if client_range:
        headers["range"] = client_range
        headers["accept-encoding"] = "identity"

    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        response_stream = urllib.request.urlopen(req, context=ctx, timeout=30)
        status_code = response_stream.status
        
        resp_headers = {}
        for k, v in response_stream.getheaders():
            kl = k.lower()
            if kl in ["content-type", "content-length", "accept-ranges", "content-range"]:
                resp_headers[k] = v

        resp_headers["Accept-Ranges"] = "bytes"

        def generate():
            try:
                while True:
                    chunk = response_stream.read(131072)
                    if not chunk:
                        break
                    yield chunk
            finally:
                response_stream.close()

        return Response(
            generate(),
            status=status_code,
            headers=resp_headers
        )
    except urllib.error.HTTPError as e:
        return f"Upstream HTTP Error: {e.code}", e.code
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
