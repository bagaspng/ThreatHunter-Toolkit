import json
from pathlib import Path
import urllib.parse

from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views import View
import requests
from rest_framework.response import Response
from rest_framework.views import APIView

import config
from core.url_validation import ProxyUrlError
from upstream_auth.selenium_refresher import BaseCookieTimeout, CookieRefreshError, InvalidRefreshTarget

from .serializers import RefreshCookiesSerializer
from . import services


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Range, Content-Type",
    "Access-Control-Expose-Headers": "Content-Length, Content-Range",
}

_CCTV_API_URL = "https://api-newseribuwajah.bandarlampungkota.go.id/cctvs"
_CCTV_API_KEY = "ParkirIlegalDetectKey2026"


def _binary_response(payload) -> HttpResponse:
    response = HttpResponse(payload.body, status=payload.status)
    for key, value in payload.headers.items():
        response[key] = value
    return response


def _streaming_response(payload) -> StreamingHttpResponse:
    body = [payload.body] if isinstance(payload.body, bytes) else payload.body
    response = StreamingHttpResponse(body, status=payload.status)
    for key, value in payload.headers.items():
        response[key] = value
    return response


def _forward_segment_headers(request) -> dict[str, str]:
    forwarded = {}
    for name in ("Range", "If-Range", "If-None-Match", "If-Modified-Since"):
        value = request.headers.get(name)
        if value:
            forwarded[name] = value
    return forwarded


def _error_response(message: str, status: int) -> HttpResponse:
    return HttpResponse(message, status=status, headers={"Access-Control-Allow-Origin": "*"})


def _load_camera_cache() -> dict | None:
    cache_path = Path(config.CAMERAS_OUTPUT_FILE)
    if not cache_path.exists():
        return None
    with cache_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_camera_cache(data: dict) -> None:
    cache_path = Path(config.CAMERAS_OUTPUT_FILE)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def _fetch_cameras_from_upstream() -> dict:
    response = requests.get(_CCTV_API_URL, headers={"x-api-key": _CCTV_API_KEY}, timeout=10)
    response.raise_for_status()
    cameras = []

    for item in response.json().get("data", []):
        camera_id = item.get("id")
        stream_path = item.get("stream_hls", "") or ""
        m3u8_url = stream_path if stream_path.startswith("http") else f"https://stream-newseribuwajah.bandarlampungkota.go.id/{stream_path}"
        cameras.append(
            {
                "id": camera_id,
                "name": item.get("nama", f"CCTV {camera_id}"),
                "category": item.get("kategori", ""),
                "address": item.get("alamat", ""),
                "status": item.get("status", ""),
                "kelurahan": item.get("kelurahan", {}).get("nama") if item.get("kelurahan") else "",
                "kecamatan": item.get("kecamatan", {}).get("nama") if item.get("kecamatan") else "",
                "m3u8_url": m3u8_url,
                "proxy_url": f"/proxy/playlist?url={urllib.parse.quote(m3u8_url, safe='')}",
                "is_active": item.get("status") == "Aktif" and bool(stream_path),
            }
        )

    return {"total": len(cameras), "cameras": cameras}


class PlayerView(View):
    def get(self, request):
        return render(request, "player.html")


class CamerasView(APIView):
    def get(self, request):
        try:
            data = _load_camera_cache() or _fetch_cameras_from_upstream()
            if not Path(config.CAMERAS_OUTPUT_FILE).exists():
                _save_camera_cache(data)
        except Exception:
            return Response({"total": 0, "cameras": [], "error": "Gagal memuat daftar kamera."}, status=503)
        return Response(data)


class PlaylistProxyView(APIView):
    def get(self, request):
        try:
            upstream_url = services.validate_proxy_url(request.query_params.get("url"))
            if not services.session_has_base_cookies():
                refresh = services.enqueue_refresh_if_needed(upstream_url)
                response = _error_response("Refresh cookie dasar sedang berjalan.", 503)
                response["Retry-After"] = "5"
                if refresh.get("task_id"):
                    response["X-Refresh-Task"] = refresh["task_id"]
                return response
            payload = services.get_hls_service().fetch_playlist(upstream_url)
        except ProxyUrlError as exc:
            return _error_response(str(exc), exc.status_code)
        except Exception:
            return _error_response("Upstream playlist error", 502)
        return _binary_response(payload)


class SegmentProxyView(APIView):
    def get(self, request):
        try:
            upstream_url = services.validate_proxy_url(request.query_params.get("url"))
            payload = services.get_hls_service().fetch_segment(upstream_url, request.headers.get("Range"), _forward_segment_headers(request))
        except ProxyUrlError as exc:
            return _error_response(str(exc), exc.status_code)
        return _streaming_response(payload)


class RefreshCookiesView(APIView):
    def post(self, request):
        serializer = RefreshCookiesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_url = serializer.validated_data.get("url") or config.PORTAL_URL
        force = serializer.validated_data.get("force", False)
        wait = serializer.validated_data.get("wait", False)

        try:
            result = services.request_cookie_refresh(target_url, force=force, wait=wait)
        except InvalidRefreshTarget as exc:
            return Response({"status": "error", "message": str(exc)}, status=400)
        except (BaseCookieTimeout, CookieRefreshError):
            return Response({"status": "failed", "message": "Refresh cookie dasar belum berhasil."}, status=503)

        http_status = result.pop("http_status", 200)
        if http_status == 503:
            result.setdefault("message", "Refresh cookie dasar belum berhasil.")
        return Response(result, status=http_status)
