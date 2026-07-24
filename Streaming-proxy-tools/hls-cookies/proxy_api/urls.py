from django.urls import path

from .views import CamerasView, PlayerView, PlaylistProxyView, RefreshCookiesView, SegmentProxyView

urlpatterns = [
    path("player", PlayerView.as_view(), name="player"),
    path("api/cameras", CamerasView.as_view(), name="cameras"),
    path("proxy/playlist", PlaylistProxyView.as_view(), name="proxy-playlist"),
    path("proxy/segment", SegmentProxyView.as_view(), name="proxy-segment"),
    path("api/refresh-cookies", RefreshCookiesView.as_view(), name="refresh-cookies"),
]
