# Realtime Network Capture (pyshark → JSON)

Script Python untuk menangkap trafik jaringan secara **real-time** dan menulis hasilnya secara live ke sebuah file JSON, menggunakan [`pyshark`](https://github.com/KimiNewt/pyshark) (wrapper Python untuk `tshark`/Wireshark).

## Fitur

- Capture paket secara live dari interface jaringan pilihan
- Update file JSON secara periodik (bukan hanya di akhir), sehingga bisa dipantau sambil capture berjalan
- Penulisan file JSON dilakukan secara *atomic* (tulis ke file sementara lalu rename), sehingga file JSON **selalu valid** meski dibuka di tengah proses capture
- Bisa difilter dengan BPF filter (contoh: `tcp port 80`)
- Bisa dibatasi jumlah maksimal record yang disimpan agar file tidak tumbuh tanpa batas
- Berhenti dengan rapi (graceful shutdown) saat ditekan `CTRL+C`

## Persyaratan

- Python 3.9 – 3.12 (disarankan; pyshark belum sepenuhnya stabil di Python 3.13/3.14)
- [Wireshark](https://www.wireshark.org/download.html) / `tshark` terinstall (menyediakan mesin capture)
- Privilege admin/root untuk melakukan capture paket

## Instalasi

### 1. Install Wireshark / tshark

**Windows:**
Download & install dari https://www.wireshark.org/download.html. Pastikan komponen **Npcap** ikut terinstall (biasanya otomatis tercentang saat instalasi) — ini yang menyediakan akses low-level ke network interface di Windows.

**Linux (Debian/Ubuntu):**
```bash
sudo apt update
sudo apt install -y tshark
```
Saat instalasi akan muncul prompt "Should non-superusers be able to capture packets?" → pilih **Yes** jika ingin capture tanpa `sudo`.

**macOS:**
```bash
brew install wireshark
```

### 2. Buat virtual environment & install dependency Python

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. (Opsional) Izin capture tanpa sudo — Linux

```bash
sudo usermod -aG wireshark $USER
sudo setcap cap_net_raw,cap_net_admin=eip $(which dumpcap)
```
Logout/login ulang agar keanggotaan grup aktif.

## Menemukan nama interface

```bash
tshark -D
```

Contoh output (Windows):
```
1. \Device\NPF_{...} (Local Area Connection* 10)
4. \Device\NPF_{...} (Wi-Fi)
7. \Device\NPF_{...} (Ethernet 2)
```

Kamu bisa memakai **nama** (`"Wi-Fi"`), **nomor index** (`4`), atau **device path lengkap** (`"\Device\NPF_{...}"`) sebagai argumen `-i`.

## Cara pakai

Jalankan dengan privilege admin/root:

```bash
# Windows (PowerShell as Administrator)
python realtime_capture.py -i "Wi-Fi" -o hasil_capture.json

# Linux/Mac
sudo python3 realtime_capture.py -i eth0 -o hasil_capture.json
```

### Opsi yang tersedia

| Argumen | Keterangan | Default |
|---|---|---|
| `-i`, `--interface` | Nama/index/device path interface jaringan (**wajib**) | – |
| `-o`, `--output` | Path file JSON output | `capture_output.json` |
| `-f`, `--filter` | BPF capture filter, contoh: `"tcp port 80"` | tidak ada |
| `--flush-interval` | Interval (detik) penulisan ke file JSON | `2.0` |
| `--max-records` | Batas maksimal jumlah record disimpan | tak terbatas |

### Contoh

```bash
# hanya capture trafik HTTP (port 80)
python realtime_capture.py -i "Wi-Fi" -o hasil_capture.json -f "tcp port 80"

# update JSON lebih sering (tiap 1 detik)
python realtime_capture.py -i "Wi-Fi" --flush-interval 1

# batasi hanya simpan 500 record terakhir
python realtime_capture.py -i "Wi-Fi" --max-records 500
```

Tekan `CTRL+C` untuk menghentikan capture. Data terakhir akan otomatis disimpan sebelum program keluar.

## Format output JSON

File output berisi array objek, satu objek per paket:

```json
[
  {
    "timestamp": "2026-07-09T14:23:01.123456",
    "frame_time": "2026-07-09T14:23:01.100000",
    "length": 66,
    "highest_layer": "TCP",
    "protocol": "IPv4",
    "src_ip": "192.168.1.10",
    "dst_ip": "142.250.72.196",
    "src_port": "51422",
    "dst_port": "443",
    "info": "TCP"
  }
]
```