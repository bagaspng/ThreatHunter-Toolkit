"""
Project configuration — constants only, no logic.
"""

# Portal utama yang berisi daftar kamera
PORTAL_URL = "https://seribuwajah.bandarlampungkota.go.id/list"

# Streaming server base (untuk Referer header)
STREAM_REFERER = "https://seribuwajah.bandarlampungkota.go.id/"

# Output files
CAMERAS_OUTPUT_FILE = "output/cameras.json"
COOKIES_CACHE_FILE  = "output/cookies_cache.json"
COOKIES_MANUAL_FILE = "cookies.json"

# Selenium cookie service (cookies-exp.py)
COOKIE_SERVICE_URL = "http://localhost:5001"

# Proxy server
PROXY_HOST = "0.0.0.0"
PROXY_PORT = 5000

# HTTP timeout (detik)
TIMEOUT = 10
