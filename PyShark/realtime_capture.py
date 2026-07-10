import argparse
import asyncio
import json
import os
import re
import sys
import threading
from datetime import datetime

import pyshark


def ensure_event_loop():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    def _silent_exception_handler(loop, context):
        exc = context.get("exception")
        if isinstance(exc, EOFError):
            return
        loop.default_exception_handler(context)

    loop.set_exception_handler(_silent_exception_handler)


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


ASCII_STRING_PATTERN = re.compile(rb"[\x20-\x7e]{4,}")


def extract_ascii_strings(raw_bytes) -> list:
    if not raw_bytes:
        return []
    return [m.decode("ascii", errors="ignore") for m in ASCII_STRING_PATTERN.findall(raw_bytes)]


def layer_to_dict(layer) -> dict:
    fields = {}
    for field_name in layer.field_names:
        try:
            value = layer.get_field_value(field_name)
        except Exception:
            value = None
        fields[field_name] = str(value) if value is not None else None
    return fields


def packet_to_dict(pkt) -> dict:
    record = {
        "timestamp": datetime.now().isoformat(),
        "frame_number": getattr(pkt, "number", None),
        "sniff_time": pkt.sniff_time.isoformat() if getattr(pkt, "sniff_time", None) else None,
        "length": pkt.length if hasattr(pkt, "length") else None,
        "highest_layer": pkt.highest_layer if hasattr(pkt, "highest_layer") else None,
        "layers": {},
        "ascii_strings": [],
    }

    for layer in pkt.layers:
        record["layers"][layer.layer_name] = layer_to_dict(layer)

    try:
        raw_bytes = pkt.get_raw_packet()
        record["ascii_strings"] = extract_ascii_strings(raw_bytes)
    except Exception:
        record["ascii_strings"] = []

    return record


def main():
    parser = argparse.ArgumentParser(description="Real-time network capture ke JSON menggunakan pyshark.")
    parser.add_argument("-i", "--interface", required=True)
    parser.add_argument("-o", "--output", default="capture_output.json")
    parser.add_argument("-f", "--filter", default=None)
    parser.add_argument("--flush-interval", type=float, default=2.0)
    parser.add_argument("--max-records", type=int, default=100)
    args = parser.parse_args()

    ensure_event_loop()

    writer = RealtimeCaptureWriter(
        output_path=args.output,
        flush_interval=args.flush_interval,
        max_records=args.max_records,
    )
    writer.start()

    capture_kwargs = {"interface": args.interface, "include_raw": True, "use_json": True}
    if args.filter:
        capture_kwargs["bpf_filter"] = args.filter

    capture = pyshark.LiveCapture(**capture_kwargs)

    print(f"[*] Memulai capture di interface '{args.interface}' ...")
    print(f"[*] Hasil akan diupdate real-time ke: {args.output}")
    print("[*] Tekan CTRL+C untuk berhenti.\n")

    exit_code = 0

    try:
        for pkt in capture.sniff_continuously():
            try:
                record = packet_to_dict(pkt)
                writer.add_packet(record)
                ip_layer = record["layers"].get("ip") or record["layers"].get("ipv6") or {}
                src = ip_layer.get("ip.src") or ip_layer.get("ipv6.src")
                dst = ip_layer.get("ip.dst") or ip_layer.get("ipv6.dst")
                print(f"[+] #{record['frame_number']} {src} -> {dst} "
                      f"[{record['highest_layer']}] len={record['length']}")
            except Exception as e:
                print(f"[!] Error memproses paket: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\n[*] Menghentikan capture, menyimpan sisa data...")
    except Exception as e:
        print(f"[!] Capture error: {e}", file=sys.stderr)
        exit_code = 1
    finally:
        try:
            capture.close()
        except Exception:
            pass
        writer.stop()
        print("[*] Selesai. File JSON final tersimpan di:", args.output)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()