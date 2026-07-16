#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import sys
import tempfile
from collections import deque
from datetime import datetime

try:
    import pyshark
except ImportError:
    sys.exit(
        "Modul 'pyshark' belum terinstall.\n"
        "Install dengan: pip install pyshark\n"
        "Pastikan juga tshark (bagian dari Wireshark) sudah terinstall di sistem."
    )

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())


def bytes_to_ascii(raw_bytes: bytes) -> str:
    return "".join(
        chr(b) if 32 <= b <= 126 else "."
        for b in raw_bytes
    )


def extract_http_detail(packet) -> dict:
    detail = {}
    if not hasattr(packet, "http"):
        return detail

    http = packet.http

    method = _safe(http, "request_method")
    if method:
        detail["type"] = "request"
        detail["method"] = method
        detail["host"] = _safe(http, "host")
        detail["uri"] = _safe(http, "request_uri")
        detail["full_uri"] = _safe(http, "request_full_uri")
        detail["user_agent"] = _safe(http, "user_agent")

    code = _safe(http, "response_code")
    if code:
        detail["type"] = "response"
        detail["status_code"] = code
        detail["status_phrase"] = _safe(http, "response_phrase")
        detail["content_type"] = _safe(http, "content_type")
        detail["content_length"] = _safe(http, "content_length")

    body_hex = _safe(http, "file_data")
    if body_hex:
        try:
            body_bytes = bytes.fromhex(body_hex.replace(":", ""))
            detail["body_ascii"] = bytes_to_ascii(body_bytes)
        except ValueError:
            pass

    return detail


def extract_payload_ascii(packet) -> str:
    payload_hex = None

    for layer_name in ("data", "tcp", "udp"):
        if hasattr(packet, layer_name):
            layer = getattr(packet, layer_name)
            if hasattr(layer, "data"):
                payload_hex = layer.data.replace(":", "")
                break
            if hasattr(layer, "payload"):
                payload_hex = layer.payload.replace(":", "")
                break

    if not payload_hex:
        return ""

    try:
        raw_bytes = bytes.fromhex(payload_hex)
        return bytes_to_ascii(raw_bytes)
    except ValueError:
        return ""


class JSONStore:
    def __init__(self, json_path: str, max_records: int = 100):
        self.json_path = json_path
        self.max_records = max_records
        self.records = deque(maxlen=max_records)

    def add(self, record: dict):
        self.records.append(record)
        self._flush()

    def _flush(self):
        directory = os.path.dirname(os.path.abspath(self.json_path)) or "."
        fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(list(self.records), f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.json_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise


def _safe(layer, field, default=None):
    return getattr(layer, field, default)


def build_packet_record(packet, index: int) -> dict:
    record = {
        "index": index,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "protocol": None,
        "length": None,
        "eth": {"src_mac": None, "dst_mac": None},
        "ip_version": None,
        "src_ip": None,
        "dst_ip": None,
        "ip_detail": {},
        "transport": None,
        "src_port": None,
        "dst_port": None,
        "transport_detail": {},
        "http_detail": {},
        "payload_ascii": "",
    }
    try:
        record["protocol"] = packet.highest_layer
        record["length"] = packet.length

        if hasattr(packet, "eth"):
            record["eth"]["src_mac"] = _safe(packet.eth, "src")
            record["eth"]["dst_mac"] = _safe(packet.eth, "dst")

        if hasattr(packet, "ip"):
            ip = packet.ip
            record["ip_version"] = "IPv4"
            record["src_ip"] = _safe(ip, "src")
            record["dst_ip"] = _safe(ip, "dst")
            record["ip_detail"] = {
                "hdr_len": _safe(ip, "hdr_len"),
                "dsfield": _safe(ip, "dsfield"),
                "total_len": _safe(ip, "len"),
                "ttl": _safe(ip, "ttl"),
                "proto": _safe(ip, "proto"),
                "flags": _safe(ip, "flags"),
                "checksum": _safe(ip, "checksum"),
            }
        elif hasattr(packet, "ipv6"):
            ip6 = packet.ipv6
            record["ip_version"] = "IPv6"
            record["src_ip"] = _safe(ip6, "src")
            record["dst_ip"] = _safe(ip6, "dst")
            record["ip_detail"] = {
                "traffic_class": _safe(ip6, "tclass"),
                "flow_label": _safe(ip6, "flow"),
                "payload_len": _safe(ip6, "plen"),
                "next_header": _safe(ip6, "nxt"),
                "hop_limit": _safe(ip6, "hlim"),
            }

        if hasattr(packet, "tcp"):
            tcp = packet.tcp
            record["transport"] = "TCP"
            record["src_port"] = _safe(tcp, "srcport")
            record["dst_port"] = _safe(tcp, "dstport")
            record["transport_detail"] = {
                "seq": _safe(tcp, "seq"),
                "ack": _safe(tcp, "ack"),
                "flags": _safe(tcp, "flags"),
                "window_size": _safe(tcp, "window_size"),
                "checksum": _safe(tcp, "checksum"),
            }
        elif hasattr(packet, "udp"):
            udp = packet.udp
            record["transport"] = "UDP"
            record["src_port"] = _safe(udp, "srcport")
            record["dst_port"] = _safe(udp, "dstport")
            record["transport_detail"] = {
                "length": _safe(udp, "length"),
                "checksum": _safe(udp, "checksum"),
            }

        record["http_detail"] = extract_http_detail(packet)
        record["payload_ascii"] = extract_payload_ascii(packet)
    except AttributeError:
        pass

    return record


def print_packet_info(record: dict):
    print(
        f"\n[{record['index']}] {record['timestamp']} | "
        f"{str(record['protocol']):<6} | "
        f"{record['src_ip']}:{record['src_port']} -> "
        f"{record['dst_ip']}:{record['dst_port']} | len={record['length']}"
    )
    if record["eth"]["src_mac"] or record["eth"]["dst_mac"]:
        print(f"    MAC            : {record['eth']['src_mac']} -> {record['eth']['dst_mac']}")
    if record["ip_version"]:
        print(f"    IP versi       : {record['ip_version']}")
        for k, v in record["ip_detail"].items():
            print(f"      {k:<14}: {v}")
    if record["transport"]:
        print(f"    Transport      : {record['transport']}")
        for k, v in record["transport_detail"].items():
            print(f"      {k:<14}: {v}")
    if record["http_detail"]:
        print("    HTTP           :")
        for k, v in record["http_detail"].items():
            print(f"      {k:<14}: {v}")
    if record["payload_ascii"]:
        print(f"    Payload (ASCII): {record['payload_ascii']}")
    else:
        print("    Payload (ASCII): <tidak ada / tidak dapat didekode>")


def live_capture(interface: str, bpf_filter: str, count: int, output_file: str,
                  json_path: str, max_records: int):
    print(f"Memulai live capture di interface '{interface}' ...")
    if bpf_filter:
        print(f"Filter BPF: {bpf_filter}")
    if count:
        print(f"Batas jumlah paket: {count}")
    if output_file:
        print(f"Paket akan disimpan ke: {output_file}")
    if json_path:
        print(f"Hasil realtime disimpan ke JSON: {json_path} (menyimpan {max_records} capture terbaru)")

    store = JSONStore(json_path, max_records) if json_path else None

    capture = pyshark.LiveCapture(
        interface=interface,
        bpf_filter=bpf_filter if bpf_filter else None,
        output_file=output_file if output_file else None,
    )

    idx = 0
    try:
        for packet in capture.sniff_continuously(packet_count=count if count else None):
            idx += 1
            record = build_packet_record(packet, idx)
            print_packet_info(record)
            if store:
                store.add(record)
    except KeyboardInterrupt:
        print("\nCapture dihentikan oleh user (Ctrl+C).")
    finally:
        capture.close()
        print(f"\nTotal paket ditangkap: {idx}")


def read_from_file(pcap_path: str, bpf_filter: str, json_path: str, max_records: int):
    print(f"Membaca paket dari file: {pcap_path}")
    if json_path:
        print(f"Hasil realtime disimpan ke JSON: {json_path} (menyimpan {max_records} capture terbaru)")

    store = JSONStore(json_path, max_records) if json_path else None

    capture = pyshark.FileCapture(pcap_path, display_filter=bpf_filter if bpf_filter else None)

    idx = 0
    for packet in capture:
        idx += 1
        record = build_packet_record(packet, idx)
        print_packet_info(record)
        if store:
            store.add(record)
    capture.close()
    print(f"\nTotal paket dibaca: {idx}")


def main():
    parser = argparse.ArgumentParser(
        description="Tangkap traffic jaringan (mirip Wireshark) dengan PyShark, termasuk payload ASCII."
    )
    parser.add_argument("-i", "--interface", help="Nama interface untuk live capture, contoh: eth0, wlan0")
    parser.add_argument("-r", "--read-file", help="Baca paket dari file .pcap/.pcapng yang sudah ada")
    parser.add_argument("-f", "--filter", default="", help="Filter BPF (live capture) atau display filter (read file)")
    parser.add_argument("-c", "--count", type=int, default=0, help="Jumlah maksimum paket yang ditangkap (0 = tanpa batas)")
    parser.add_argument("-o", "--output", default="", help="Simpan hasil live capture ke file .pcap")
    parser.add_argument("-j", "--json-output", default="", help="Simpan hasil capture ke file JSON secara realtime")
    parser.add_argument("--max-records", type=int, default=100,
                         help="Jumlah capture terbaru yang disimpan di file JSON (default: 100)")

    args = parser.parse_args()

    if args.read_file:
        read_from_file(args.read_file, args.filter, args.json_output, args.max_records)
    elif args.interface:
        live_capture(args.interface, args.filter, args.count, args.output,
                     args.json_output, args.max_records)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()