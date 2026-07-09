import argparse
import asyncio
import json
import os
import signal
import sys
import threading
from datetime import datetime

import pyshark


def ensure_event_loop():
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)


class RealtimeCaptureWriter:
    def __init__(self, output_path: str, flush_interval: float = 2.0, max_records: int = None):
        self.output_path = output_path
        self.flush_interval = flush_interval
        self.max_records = max_records
        self.records = []
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)

    def start(self):
        self._writer_thread.start()

    def stop(self):
        self._stop_event.set()
        self._writer_thread.join(timeout=self.flush_interval + 2)
        self._flush_to_disk()

    def add_packet(self, record: dict):
        with self.lock:
            self.records.append(record)
            if self.max_records and len(self.records) > self.max_records:
                self.records = self.records[-self.max_records:]

    def _writer_loop(self):
        while not self._stop_event.is_set():
            self._flush_to_disk()
            self._stop_event.wait(self.flush_interval)

    def _flush_to_disk(self):
        with self.lock:
            data_snapshot = list(self.records)
        tmp_path = self.output_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data_snapshot, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.output_path)
        except Exception as e:
            print(f"[!] Gagal menulis ke {self.output_path}: {e}", file=sys.stderr)


def packet_to_dict(pkt) -> dict:
    record = {
        "timestamp": datetime.now().isoformat(),
        "frame_time": getattr(pkt, "sniff_time", None).isoformat() if getattr(pkt, "sniff_time", None) else None,
        "length": int(pkt.length) if hasattr(pkt, "length") else None,
        "highest_layer": pkt.highest_layer if hasattr(pkt, "highest_layer") else None,
        "protocol": None,
        "src_ip": None,
        "dst_ip": None,
        "src_port": None,
        "dst_port": None,
        "info": None,
    }

    try:
        if hasattr(pkt, "ip"):
            record["src_ip"] = pkt.ip.src
            record["dst_ip"] = pkt.ip.dst
            record["protocol"] = "IPv4"
        elif hasattr(pkt, "ipv6"):
            record["src_ip"] = pkt.ipv6.src
            record["dst_ip"] = pkt.ipv6.dst
            record["protocol"] = "IPv6"
    except AttributeError:
        pass

    try:
        if hasattr(pkt, "tcp"):
            record["src_port"] = pkt.tcp.srcport
            record["dst_port"] = pkt.tcp.dstport
            record["info"] = "TCP"
        elif hasattr(pkt, "udp"):
            record["src_port"] = pkt.udp.srcport
            record["dst_port"] = pkt.udp.dstport
            record["info"] = "UDP"
    except AttributeError:
        pass

    return record


def main():
    parser = argparse.ArgumentParser(description="Real-time network capture ke JSON menggunakan pyshark.")
    parser.add_argument("-i", "--interface", required=True)
    parser.add_argument("-o", "--output", default="capture_output.json")
    parser.add_argument("-f", "--filter", default=None)
    parser.add_argument("--flush-interval", type=float, default=2.0)
    parser.add_argument("--max-records", type=int, default=None)
    args = parser.parse_args()

    ensure_event_loop()

    writer = RealtimeCaptureWriter(
        output_path=args.output,
        flush_interval=args.flush_interval,
        max_records=args.max_records,
    )
    writer.start()

    capture_kwargs = {"interface": args.interface}
    if args.filter:
        capture_kwargs["bpf_filter"] = args.filter

    capture = pyshark.LiveCapture(**capture_kwargs)

    print(f"[*] Memulai capture di interface '{args.interface}' ...")
    print(f"[*] Hasil akan diupdate real-time ke: {args.output}")
    print("[*] Tekan CTRL+C untuk berhenti.\n")

    def handle_sigint(sig, frame):
        print("\n[*] Menghentikan capture, menyimpan sisa data...")
        writer.stop()
        print("[*] Selesai. File JSON final tersimpan di:", args.output)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        for pkt in capture.sniff_continuously():
            try:
                record = packet_to_dict(pkt)
                writer.add_packet(record)
                print(f"[+] {record['timestamp']} {record.get('src_ip')}:{record.get('src_port')} -> "
                      f"{record.get('dst_ip')}:{record.get('dst_port')} ({record.get('highest_layer')})")
            except Exception as e:
                print(f"[!] Error memproses paket: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[!] Capture error: {e}", file=sys.stderr)
        writer.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()