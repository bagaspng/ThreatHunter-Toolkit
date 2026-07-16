import os
import zipfile
import hashlib
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.panel import Panel
from PIL import Image
import piexif
from pypdf import PdfReader, PdfWriter

console = Console()
ALLOWED = {".jpg", ".jpeg", ".png", ".pdf", ".docx", ".xlsx"}

def get_ext(path):
    return os.path.splitext(path)[1].lower()

def calc_hashes(path):
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
    return md5.hexdigest(), sha1.hexdigest(), sha256.hexdigest()

def view_image(path):
    table = Table(title="Image Metadata")
    table.add_column("Category", style="yellow")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="magenta")
    
    # --- File Category ---
    sz = os.path.getsize(path)
    md5, sha1, sha256 = calc_hashes(path)
    table.add_row("File", "FileSize", f"{sz} Bytes ({sz/1024:.2f} kB)")
    table.add_row("File", "FileTypeExtension", get_ext(path)[1:])
    table.add_row("File", "MD5", md5)
    table.add_row("File", "SHA1", sha1)
    table.add_row("File", "SHA256", sha256)

    img = Image.open(path)
    info = img.info
    
    # --- Composite Category ---
    table.add_row("Composite", "ImageSize", f"{img.width}x{img.height}")
    table.add_row("Composite", "Megapixels", f"{(img.width * img.height) / 1000000:.3f}")
    
    # --- JFIF/Basic Category ---
    has_basic = False
    for k, v in info.items():
        if k != 'exif':
            has_basic = True
            table.add_row("JFIF / Basic", str(k), str(v)[:100])
    if not has_basic:
        table.add_row("JFIF / Basic", "-", "-")
            
    # --- EXIF Category ---
    has_exif = False
    if get_ext(path) in ['.jpg', '.jpeg']:
        try:
            exif = piexif.load(path)
            for ifd in ("0th", "Exif", "GPS", "1st", "Interop"):
                if ifd in exif and exif[ifd]:
                    for tag in exif[ifd]:
                        try:
                            tag_name = piexif.TAGS[ifd][tag]["name"]
                        except KeyError:
                            tag_name = f"Unknown ({tag})"
                        val = exif[ifd][tag]
                        
                        if isinstance(val, bytes):
                            try:
                                val_str = val.decode('utf-8', errors='ignore')
                            except:
                                val_str = str(val)
                        else:
                            val_str = str(val)
                            
                        if len(val_str) > 100: val_str = val_str[:97] + "..."
                        table.add_row(f"EXIF - {ifd}", tag_name, val_str)
                        has_exif = True
        except Exception as e:
            # Not an error if it just doesn't have EXIF.
            if "No exif data" not in str(e).lower() and "empty" not in str(e).lower():
                table.add_row("Error", "EXIF Parsing", str(e))
            
    if not has_exif:
        table.add_row("EXIF", "-", "-")
        
    console.print(table)

def strip_image(path, out):
    img = Image.open(path)
    data = list(img.getdata())
    clean = Image.new(img.mode, img.size)
    clean.putdata(data)
    clean.save(out)

def add_image(path, out, key, val):
    # ponytail: naive add. JPG only via piexif for simplicity. PNG needs chunk parsing.
    if get_ext(path) not in ['.jpg', '.jpeg']:
        console.print("[red]Add metadata only supported for JPG right now.[/red]")
        return
    img = Image.open(path)
    # Some JPEGs keep raw EXIF in app1 block which `info` misses if strictly JFIF.
    # piexif.load directly from file path is safer for extraction.
    try:
        exif_raw = piexif.load(path)
    except Exception:
        exif_raw = None

    if not exif_raw:
        # File has no EXIF at all, start fresh
        exif = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "Interop": {}}
    else:
        exif = exif_raw
            
    # Inject into standard Software or DocumentName tag
    # User inputs are strings. DocumentName is safe for ASCII.
    
    # Map friendly keys to EXIF tag IDs (0th IFD)
    tag_map = {
        "artist": piexif.ImageIFD.Artist,
        "copyright": piexif.ImageIFD.Copyright,
        "documentname": piexif.ImageIFD.DocumentName,
        "imagedescription": piexif.ImageIFD.ImageDescription,
        "make": piexif.ImageIFD.Make,
        "model": piexif.ImageIFD.Model,
        "software": piexif.ImageIFD.Software
    }
    
    k_lower = key.lower().strip()
    if k_lower in tag_map:
        tag_id = tag_map[k_lower]
        exif["0th"][tag_id] = val.encode('utf-8')
    else:
        # Fallback if key unknown
        console.print(f"[yellow]Key '{key}' not in quick map. Defaulting to DocumentName.[/yellow]")
        exif["0th"][piexif.ImageIFD.DocumentName] = val.encode('utf-8')
        
    # JFIF drops EXIF if not handled carefully during save.
    try:
        exif_bytes = piexif.dump(exif)
        # Re-save with original format and new EXIF. Keep quality high so hash doesn't just change from compression.
        img.save(out, format='JPEG', exif=exif_bytes, quality=95)
    except Exception as e:
        console.print(f"[red]Failed to add EXIF: {e}[/red]")
        img.save(out, format='JPEG')

def view_pdf(path):
    reader = PdfReader(path)
    meta = reader.metadata
    table = Table(title="PDF Metadata")
    table.add_column("Category", style="yellow")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="magenta")
    
    # Document Info Dictionary
    if meta:
        for k, v in meta.items():
            table.add_row("DocInfo", str(k), str(v)[:100])
            
    # XMP Metadata (if available)
    try:
        xmp = reader.xmp_metadata
        if xmp:
            table.add_row("XMP", "Has XMP", "True")
            if hasattr(xmp, 'dc_creator'):
                table.add_row("XMP", "Creator", str(xmp.dc_creator))
            if hasattr(xmp, 'dc_description'):
                table.add_row("XMP", "Description", str(xmp.dc_description))
    except Exception:
        pass
        
    console.print(table)

def strip_pdf(path, out):
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    with open(out, "wb") as f:
        writer.write(f)

def add_pdf(path, out, key, val):
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    meta = reader.metadata or {}
    meta[f"/{key}"] = val
    writer.add_metadata(meta)
    with open(out, "wb") as f:
        writer.write(f)

import xml.etree.ElementTree as ET

def view_office(path):
    table = Table(title="Office Metadata (docProps)")
    table.add_column("Category", style="yellow")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="magenta")
    with zipfile.ZipFile(path, 'r') as zin:
        for item in zin.namelist():
            if item.startswith("docProps/"):
                try:
                    xml_data = zin.read(item)
                    root = ET.fromstring(xml_data)
                    for child in root:
                        tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                        text_val = child.text.strip() if child.text and child.text.strip() else "(empty)"
                        table.add_row(item, tag_name, text_val[:100])
                except Exception:
                    table.add_row(item, "Status", "Could not parse XML")
    console.print(table)

def strip_office(path, out):
    with zipfile.ZipFile(path, 'r') as zin:
        with zipfile.ZipFile(out, 'w') as zout:
            for item in zin.namelist():
                if not item.startswith("docProps/"):
                    zout.writestr(item, zin.read(item))

def main():
    console.print(Panel("[bold green]Metadata Tool[/bold green]\nView, Strip, Add."))
    
    while True:
        path = Prompt.ask("Enter file path (or 'q' to quit)")
        if path.lower() == 'q': break
        
        if not os.path.exists(path):
            console.print("[red]File not found.[/red]")
            continue
            
        ext = get_ext(path)
        if ext not in ALLOWED:
            console.print(f"[red]Ext {ext} not allowed. Use: {ALLOWED}[/red]")
            continue
            
        while True:
            console.print("\n[yellow]1. View | 2. Strip | 3. Add | 4. Back[/yellow]")
            choice = Prompt.ask("Choose", choices=["1", "2", "3", "4"])
            
            out_path = f"mod_{os.path.basename(path)}"
            
            if choice == "4":
                break
                
            if choice == "1":
                if ext in ['.jpg', '.jpeg', '.png']: view_image(path)
                elif ext == '.pdf': view_pdf(path)
                else: view_office(path)
                
            elif choice == "2":
                if ext in ['.jpg', '.jpeg', '.png']: strip_image(path, out_path)
                elif ext == '.pdf': strip_pdf(path, out_path)
                else: strip_office(path, out_path)
                console.print(f"[green]Saved cleaned file: {out_path}[/green]")
                
            elif choice == "3":
                if ext in ['.docx', '.xlsx']:
                    console.print("[red]Add metadata skipped for Office docs. Need full XML rewrite.[/red]")
                    continue
                console.print("\n[dim]Image Keys: Artist, Copyright, DocumentName, ImageDescription, Make, Model, Software[/dim]")
                console.print("[dim]PDF Keys: Author, Creator, Subject, Title, etc.[/dim]")
                k = Prompt.ask("Metadata Key")
                v = Prompt.ask("Metadata Value")
                if ext in ['.jpg', '.jpeg', '.png']: add_image(path, out_path, k, v)
                elif ext == '.pdf': add_pdf(path, out_path, k, v)
                console.print(f"[green]Saved injected file: {out_path}[/green]")

if __name__ == "__main__":
    main()
