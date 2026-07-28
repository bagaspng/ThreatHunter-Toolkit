"""
ProxyForge CLI
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
import logging

from proxyforge.core.validator import ProxyValidator
from proxyforge.core.pool import ProxyPool
from proxyforge.core.rotator import ProxyRotator

def setup_logger() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    # Sembunyikan pesan error internal dari asyncio di Windows (seperti ConnectionResetError)
    if sys.platform == "win32":
        logging.getLogger("asyncio").setLevel(logging.CRITICAL)

async def run_validation_pipeline(validator: ProxyValidator) -> None:
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [*] Memulai proses pencarian dan validasi proksi...")
    
    alive = await validator.run()
    
    total_checked = getattr(validator, "last_total_checked", len(alive))
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [+] Selesai! Ditemukan {len(alive)} proxy hidup dari {total_checked} proxy yang diuji.")
    
    pool = ProxyPool.build(alive)
    pool_path = "working_proxies.json"
    pool.save(pool_path)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [+] Pool berhasil disimpan ke '{pool_path}' ({len(pool.proxies)} proxy aktif).")
    
    summary = pool.summary()
    alive_pct = round(summary["count"] / max(1, total_checked) * 100, 2)
    
    report_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_checked": total_checked,
        "alive_count": summary["count"],
        "alive_percentage": alive_pct,
        "summary": summary
    }
    
    with open("report.json", "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [i] Statistik laporan disimpan ke 'report.json'\n")

def cmd_validate(args: argparse.Namespace) -> None:
    min_anon = tuple(args.anonymity) if args.anonymity else ("elite", "anonymous", "unknown")
    
    validator = ProxyValidator(
        timeout=args.timeout, 
        concurrency=args.concurrency,
        min_anonymity=min_anon
    )
    
    if getattr(args, "daemon", False):
        print(f"\n[~] Memulai auto-refresh daemon (interval: {args.interval} detik)\n")
        async def daemon_loop():
            while True:
                await run_validation_pipeline(validator)
                print(f"[Zzz] Menunggu siklus berikutnya selama {args.interval} detik...")
                await asyncio.sleep(args.interval)
        try:
            asyncio.run(daemon_loop())
        except KeyboardInterrupt:
            print("\n[-] Daemon dihentikan oleh pengguna.")
    else:
        asyncio.run(run_validation_pipeline(validator))

def cmd_fetch(args: argparse.Namespace) -> None:
    pool_path = "working_proxies.json"
    try:
        pool = ProxyPool.load(pool_path)
    except FileNotFoundError:
        print("\n[x] Error: File working_proxies.json tidak ditemukan. Harap jalankan 'python main.py validate' terlebih dahulu.\n")
        sys.exit(1)
        
    if pool.summary()["count"] == 0:
        print("\n[x] Error: Pool kosong. Jalankan 'python main.py validate' terlebih dahulu.\n")
        sys.exit(1)
        
    rotator = ProxyRotator(pool, max_retries=args.retries)
    print(f"\n[>] Mengakses URL: {args.url} menggunakan rotator ({args.count} kali bergiliran)...")
    
    for i in range(1, args.count + 1):
        print(f"\n--- [ Request ke-{i} dari {args.count} ] ---")
        response = rotator.fetch(args.url, timeout=args.timeout)
        
        if response:
            print(f"[+] Sukses! (Status Code: {response.status_code})")
            snippet = response.text[:200].replace('\n', ' ')
            print(f"    Snippet: {snippet}{' ...[truncated]' if len(response.text) > 200 else ''}")
        else:
            print("[x] Error: Fetch gagal karena seluruh IP pengganti mati/timeout.")
    print("\n[i] Seluruh siklus request selesai.\n")

def cmd_info(args: argparse.Namespace) -> None:
    pool_path = "working_proxies.json"
    try:
        pool = ProxyPool.load(pool_path)
        print("\n[i] Informasi Pool Aktif:")
        print(json.dumps(pool.summary(), indent=2))
        print("")
    except FileNotFoundError:
        print("\n[x] Error: File working_proxies.json tidak ditemukan. Belum ada proxy yang divalidasi.\n")

def main() -> int:
    setup_logger()
    parser = argparse.ArgumentParser(prog="python main.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    p_val = subparsers.add_parser("validate", help="Jalankan pencarian dan validasi IP proxy secara agregat")
    p_val.add_argument("--timeout", type=int, default=8, help="Maksimal waktu tunggu per IP (detik). Default: 8")
    p_val.add_argument("--concurrency", type=int, default=100, help="Jumlah validasi IP paralel sekaligus. Default: 100")
    p_val.add_argument("--anonymity", nargs='+', default=["elite", "anonymous", "unknown"], help="Filter anonimitas (contoh: elite anonymous unknown)")
    p_val.add_argument("--daemon", action="store_true", help="Jalankan di background secara terus menerus (auto-refresh)")
    p_val.add_argument("--interval", type=int, default=1800, help="Interval waktu jeda siklus daemon (detik). Default: 1800 (30 menit)")
    
    p_fetch = subparsers.add_parser("fetch", help="Akses sebuah URL menggunakan proxy aktif dari pool secara aman")
    p_fetch.add_argument("url", help="Alamat web target yang ingin diakses")
    p_fetch.add_argument("--count", type=int, default=1, help="Berapa kali mengakses target (otomatis ganti proxy). Default: 1")
    p_fetch.add_argument("--retries", type=int, default=3, help="Batas toleransi mengulang ganti proxy jika IP mati. Default: 3")
    p_fetch.add_argument("--timeout", type=int, default=10, help="Waktu tunggu (detik) akses ke web target. Default: 10")
    
    p_info = subparsers.add_parser("info", help="Lihat statistik dan informasi negara dari pool proxy saat ini")
    
    args = parser.parse_args()
    
    if args.command == "validate":
        cmd_validate(args)
    elif args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "info":
        cmd_info(args)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
