"""
Project configuration â€” constants only, no logic.
"""

# Portal utama yang berisi daftar kamera
PORTAL_URL = "https://seribuwajah.bandarlampungkota.go.id/list"

# Streaming server base (untuk Referer header)
STREAM_REFERER = "https://seribuwajah.bandarlampungkota.go.id/"

# Output files
CAMERAS_OUTPUT_FILE = "output/cameras.json"
COOKIES_CACHE_FILE  = "output/cookies_cache.json"
COOKIES_MANUAL_FILE = "cookies.json"

# Hostname yang boleh dipakai sebagai target refresh Selenium internal
ALLOWED_COOKIE_REFRESH_HOSTS = (
    "seribuwajah.bandarlampungkota.go.id",
    "stream-newseribuwajah.bandarlampungkota.go.id",
)
# Proxy server
PROXY_HOST = "0.0.0.0"
PROXY_PORT = 5000

# HTTP timeout (detik)
TIMEOUT = 10



#  Segment cache policy
SEGMENT_CACHE_TTL_SECONDS = 300
SEGMENT_CACHE_MAX_FILES = 500

