"""
Data models for camera/stream entries.
"""
from dataclasses import dataclass, field


@dataclass
class Camera:
    id: int
    name: str
    m3u8_url: str
    status: str = "unknown"
    category: str = ""
    address: str = ""
    kelurahan: str = ""
    kecamatan: str = ""
    is_active: bool = False

    def to_dict(self, proxy_base: str = "") -> dict:
        import urllib.parse
        proxy_url = (
            f"{proxy_base}/proxy/playlist?url={urllib.parse.quote(self.m3u8_url, safe='')}"
            if self.m3u8_url else ""
        )
        return {
            "id":        self.id,
            "name":      self.name,
            "category":  self.category,
            "address":   self.address,
            "status":    self.status,
            "kelurahan": self.kelurahan,
            "kecamatan": self.kecamatan,
            "m3u8_url":  self.m3u8_url,
            "proxy_url": proxy_url,
            "is_active": self.is_active,
        }
