"""URL validation for proxyable upstream resources."""

from __future__ import annotations

import ipaddress
import urllib.parse


class ProxyUrlError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _is_private_or_local(hostname: str) -> bool:
    lowered = hostname.lower().rstrip(".")
    if lowered in {"localhost", "localhost.localdomain"}:
        return True
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local or address.is_reserved


def validate_proxy_url(raw_url: str | None, allowed_hosts: set[str]) -> str:
    if not raw_url:
        raise ProxyUrlError("Missing 'url' parameter", 400)

    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ProxyUrlError("Invalid URL", 400)
    if parsed.username or parsed.password:
        raise ProxyUrlError("Invalid URL", 400)

    hostname = parsed.hostname.lower()
    normalized_hosts = {host.lower() for host in allowed_hosts}
    if hostname not in normalized_hosts:
        raise ProxyUrlError("URL host is not allowed", 403)
    if _is_private_or_local(hostname) and hostname not in normalized_hosts:
        raise ProxyUrlError("URL host is not allowed", 403)

    return urllib.parse.urlunparse(parsed._replace(netloc=parsed.netloc.lower()))


def validate_redirect_location(base_url: str, location: str | None, allowed_hosts: set[str]) -> str:
    if not location:
        raise ProxyUrlError("Invalid upstream redirect", 502)
    redirected = urllib.parse.urljoin(base_url, location)
    try:
        return validate_proxy_url(redirected, allowed_hosts)
    except ProxyUrlError as exc:
        if exc.status_code == 403:
            raise ProxyUrlError("Upstream redirect host is not allowed", 403) from exc
        raise ProxyUrlError("Invalid upstream redirect", 502) from exc