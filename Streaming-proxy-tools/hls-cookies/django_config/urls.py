from django.urls import include, path

urlpatterns = [
    path("", include("proxy_api.urls")),
]