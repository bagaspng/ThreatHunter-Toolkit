import traceback
from curl_cffi import requests

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
    print("--- 1. Fetching Variant Playlist ---")
    r_var = requests.get(variant_url, headers=headers, verify=False, impersonate="chrome")
    print("Variant playlist status:", r_var.status_code)
    if r_var.status_code != 200:
        print("Failed to fetch variant playlist!")
        print(r_var.text[:500])
        exit(1)
        
    segment_urls = [line for line in r_var.text.splitlines() if line.startswith("http")]
    print(f"Total segments found: {len(segment_urls)}")
    
    if len(segment_urls) <= 38:
        print(f"Variant playlist only has {len(segment_urls)} segments, segment #38 is out of range!")
        # Let's print the last 5 segments
        print("Last 5 segments:")
        for url in segment_urls[-5:]:
            print("  ", url[:100] + "...")
        exit(1)
        
    target_segment = segment_urls[38]
    print("Segment #38 URL:", target_segment[:100] + "...")
    
    print("\n--- 2. Fetching Segment #38 ---")
    r_seg = requests.get(target_segment, headers=headers, stream=True, verify=False, impersonate="chrome")
    print("Segment status:", r_seg.status_code)
    print("Segment headers:")
    for k, v in r_seg.headers.items():
        print(f"  {k}: {v}")
        
    total_bytes = 0
    chunks_count = 0
    for chunk in r_seg.iter_content(chunk_size=65536):
        total_bytes += len(chunk)
        chunks_count += 1
        if chunks_count <= 3:
            print(f"  Chunk {chunks_count}: {len(chunk)} bytes")
            
    print(f"Successfully downloaded segment #38! Total size: {total_bytes} bytes in {chunks_count} chunks.")

except Exception as e:
    print("\n[ERROR] Exception occurred during diagnostics:")
    traceback.print_exc()
