import traceback
import urllib.request
import ssl
from curl_cffi import requests as curl_requests

headers = {
    "Accept": "*/*",
    "Accept-Encoding": "identity",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://199.87.210.226",
    "Referer": "https://199.87.210.226/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
}

variant_url = "https://datura.groovy.monster/stream/variant/AJZ2MQxlZGMzMzLlBTIuAGyxAQVjZGR3MTSuAQxlA2D5MQL3ATSzLwVmZJV0AGV1Zmp0ZGx1MQt4BGyxLwEuAl5FMJShZRueEySzFmZlG2tgAQOwpwA3YyuUHap3ERkKHKSAGzubLJVjEKb4qKbmoTx5YKIHrxMGEwM1K2ubEHSIAIt5pyISMTS4rwACpy8lHKV0rIyxISN/AQqzMwyyZGV2ZwOvMwyvAmRjMGOwMGEyLGWvZmAvZwWvAwHlZTMwBJSvBTH2MGWvZQuxLwZjBGHmZzZ4ZwWwZF5bqURjEJqWq3uJox1BL3ysBJkKBJuOYayQqJghDKWXpyu1nx44IJ9iHJjgAKp/AQp4Z2D5LwMxLGH5MGZ4L2WwMwZ0AmZkZTSzAmWwMJWwZQWuLzLjLGVjL2WyBGyyAmywBJWxZmL2AGN4MQx5MF5yrTZ4nRuErRyLD3SIG2AnE1x3JJEOYz5TG1N3qJufJySCMTAmFUSuZaEUJxA0DGHgATyhJz0kA3RlLKA2ZTEVLwuIp25yI2kwDJ55ZRAHE3WhFRMEFTb.m3u8"

try:
    print("--- Fetching Variant Playlist (using curl_cffi) ---")
    r_var = curl_requests.get(variant_url, headers=headers, verify=False, impersonate="chrome")
    segment_urls = [line for line in r_var.text.splitlines() if line.startswith("http")]
    target_segment = segment_urls[38]
    print("Segment #38 URL:", target_segment[:100] + "...")
    
    print("\n--- Test 2: Fetching Segment using built-in urllib ---")
    
    # Disable SSL verification for testing
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(target_segment, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
        print("Urllib status:", response.status)
        print("Urllib headers:")
        for k, v in response.getheaders():
            print(f"  {k}: {v}")
            
        total_bytes = 0
        chunks_count = 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            total_bytes += len(chunk)
            chunks_count += 1
            if chunks_count <= 3:
                print(f"  Chunk {chunks_count}: {len(chunk)} bytes")
            if total_bytes > 5 * 1024 * 1024:
                print("Successfully streamed 5MB using urllib!")
                break
                
        print(f"Total downloaded: {total_bytes} bytes in {chunks_count} chunks.")

except Exception as e:
    print("\n[ERROR] Exception occurred during urllib test:")
    traceback.print_exc()
