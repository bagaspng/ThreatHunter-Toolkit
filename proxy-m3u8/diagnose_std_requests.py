import traceback
import requests as std_requests
from curl_cffi import requests as curl_requests

headers = {
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
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
}

variant_url = "https://datura.groovy.monster/stream/variant/AJZ2MQxlZGMzMzLlBTIuAGyxAQVjZGR3MTSuAQxlA2D5MQL3ATSzLwVmZJV0AGV1Zmp0ZGx1MQt4BGyxLwEuAl5FMJShZRueEySzFmZlG2tgAQOwpwA3YyuUHap3ERkKHKSAGzubLJVjEKb4qKbmoTx5YKIHrxMGEwM1K2ubEHSIAIt5pyISMTS4rwACpy8lHKV0rIyxISN/AQqzMwyyZGV2ZwOvMwyvAmRjMGOwMGEyLGWvZmAvZwWvAwHlZTMwBJSvBTH2MGWvZQuxLwZjBGHmZzZ4ZwWwZF5bqURjEJqWq3uJox1BL3ysBJkKBJuOYayQqJghDKWXpyu1nx44IJ9iHJjgAKp/AQp4Z2D5LwMxLGH5MGZ4L2WwMwZ0AmZkZTSzAmWwMJWwZQWuLzLjLGVjL2WyBGyyAmywBJWxZmL2AGN4MQx5MF5yrTZ4nRuErRyLD3SIG2AnE1x3JJEOYz5TG1N3qJufJySCMTAmFUSuZaEUJxA0DGHgATyhJz0kA3RlLKA2ZTEVLwuIp25yI2kwDJ55ZRAHE3WhFRMEFTb.m3u8"

try:
    print("--- Fetching Variant Playlist (using curl_cffi) ---")
    r_var = curl_requests.get(variant_url, headers=headers, verify=False, impersonate="chrome")
    segment_urls = [line for line in r_var.text.splitlines() if line.startswith("http")]
    target_segment = segment_urls[38]
    print("Segment #38 URL:", target_segment[:100] + "...")
    
    print("\n--- Test 1: Fetching Segment using standard requests (with stream=True) ---")
    # Standard requests has no impersonate flag
    r_seg = std_requests.get(target_segment, headers=headers, stream=True, verify=False, timeout=10)
    print("Standard requests status:", r_seg.status_code)
    print("Standard requests headers:", dict(r_seg.headers))
    
    total_bytes = 0
    chunks_count = 0
    for chunk in r_seg.iter_content(chunk_size=65536):
        total_bytes += len(chunk)
        chunks_count += 1
        if chunks_count <= 3:
            print(f"  Chunk {chunks_count}: {len(chunk)} bytes")
        if total_bytes > 5 * 1024 * 1024: # stop after 5MB to verify it works
            print("Successfully streamed 5MB, standard requests works!")
            break
            
    print(f"Total downloaded: {total_bytes} bytes in {chunks_count} chunks.")

except Exception as e:
    print("\n[ERROR] Exception occurred during standard requests test:")
    traceback.print_exc()
