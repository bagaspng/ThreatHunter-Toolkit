from rest_framework import serializers


class RefreshCookiesSerializer(serializers.Serializer):
    url = serializers.URLField(required=False, allow_blank=False)
    force = serializers.BooleanField(required=False, default=False)
    wait = serializers.BooleanField(required=False, default=True)