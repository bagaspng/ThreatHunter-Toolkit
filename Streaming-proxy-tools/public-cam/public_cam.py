import concurrent.futures
import json
import os
import random
import sys
import time
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup
from colorama import Fore, Style, init

init(autoreset=True)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
]

INSECAM_BASE = "http://www.insecam.org/en"

CAMERA_DORKS = [
    # Axis Communications
    'inurl:"/view/index.shtml"',
    'inurl:"/view/view.shtml"',
    'intitle:"Live View / - AXIS"',
    "inurl:axis-cgi/jpg",
    "inurl:axis-cgi/mjpg",
    'intitle:"AXIS 240 Camera Server"',
    'intitle:"Live View / - AXIS 206M"',
    'intitle:"Live View / - AXIS 210"',
    'intitle:"Live View / - AXIS 211"',
    'intitle:"Live View / - AXIS 213 PTZ"',
    'intitle:"Live View / - AXIS 206W"',
    'intitle:"Live View / - AXIS 210W"',
    "inurl:indexFrame.shtml Axis",
    'intitle:"Axis 2400 Video Server"',
    "inurl:/view/indexFrame.shtml",
    'intitle:"live view" intitle:axis',
    'intitle:axis intitle:"video server"',
    'tilt intitle:"Live View / - AXIS" | inurl:view/view.shtml',
    'intitle:"AXIS 240 Camera Server" intext:"server push" -help',
    'intitle:"Live View /- AXIS" |inurl:view/view.shtml OR inurl:view/indexFrame.shtml |intitle:"MJPG Live Demo" |intext:"Select preset position"',
    'allintitle:Axis 2.10 OR 2.12 OR 2.30 OR 2.31 OR 2.32 OR 2.33 OR 2.34 OR 2.40 OR 2.42 OR 2.43 "Network Camera"',
    'intitle:"Live View/ — AXIS"',
    'intitle:"Live View/ — AX|S"',
    'intitle:"Live View / - AXIS 706W"',
    "AXIS Camera exploit",
    # Hikvision
    'intitle:"Hikvision Web Cameras"',
    'inurl:"/doc/page/login.asp" intext:"Hikvision"',
    'intitle:"Hikvision" inurl:"login.asp"',
    'inurl:"/onvif-http/snapshot?auth="',
    'product:"Hikvision IP Camera"',
    # Mobotix
    'inurl:"/cgi-bin/guestimage.html"',
    'inurl:"/control/faststream.jpg"',
    'intitle:"MOBOTIX" inurl:"/control/userimage.html"',
    "(intitle:MOBOTIX intitle:PDAS) | (intitle:MOBOTIX intitle:Seiten)",
    "inurl:/pda/index.html +camera",
    # Foscam
    'intitle:"Foscam" inurl:"login.htm"',
    'inurl:"/videostream.cgi?user="',
    'intitle:"Foscam" inurl:"/live.htm"',
    # Panasonic
    'inurl:"/CgiStart?page=Single"',
    'intitle:"Panasonic Network Camera"',
    'inurl:"/nphMotionJpeg?Resolution="',
    'inurl:/config/cam_portal.cgi "Panasonic"',
    'inurl:"/ViewerFrame?Mode="',
    'inurl:"/ViewerFrame?Mode=Motion"',
    'intitle:"Panasonic" inurl:"ViewerFrame?Mode="',
    'inurl:"MultiCameraFrame?Mode=Motion"',
    'inurl:"WJ-NTI 04 Main Page"',
    'inurl:/live.htm intext:"M-JPEG"|"System Log"|"Camera-1"|"View Control"',
    # D-Link
    'intitle:"D-Link" inurl:"/video.htm"',
    'inurl:"/mjpg/video.cgi" intitle:"D-Link"',
    'intitle:"D-Link DCS-"',
    'inurl:"/eng/admin/adv_audiovideo.cgi"',
    # Sony
    'intitle:"sony network camera snc-pl"',
    'intitle:"Sony" inurl:"/home/homeJ.html"',
    'intitle:"SNC-RZ30" -demo',
    'intitle:"sony network camera snc-ml"',
    'inurl:"/image/webcam.jpg" intitle:"Sony"',
    "intitle:snc-220 inurl:home/",
    "intitle:snc-cs3 inurl:home/",
    "intitle:snc-r230 inurl:home/",
    # Canon
    'intitle:"Network Camera VB-M600"',
    'inurl:"/sample/LvAppl/lvappl.htm"',
    'inurl:"lvappl.htm"',
    'inurl:"/view.shtml" "camera"',
    # Vivotek
    "server:VVTK-HTTP-Server",
    'inurl:"/cgi-bin/viewer/video.jpg"',
    # WebcamXP / Webcam 7
    'intitle:"webcamXP 5"',
    'intitle:"webcam 7"',
    'intext:"powered by webcamXP 5"',
    'inurl:"/cam_1.jpg" intitle:"webcamXP"',
    'intitle:"webcam 7" inurl:"/gallery.html"',
    'intitle:"webcamXP 5" -download',
    'intitle:"webcam 7" inurl:"8080" -intext:"8080"',
    "intitle:\"webcamXP 5\" inurl:8080 'Live'",
    'intitle:"WEBCAM 7 " -inurl:/admin.html',
    # Dahua
    'intitle:"Dahua IP Camera" inurl:/login',
    "inurl:dahua inurl:view/view.shtml",
    'intitle:"Dahua" inurl:"/cgi-bin/rpc.cgi?action=login"',
    'intext:"Dahua" intitle:"Network Camera" inurl:main.cgi',
    # Reolink
    'intitle:"Reolink" inurl:view',
    'intitle:"Reolink Camera" inurl:login',
    'intitle:"Reolink" inurl:snapshot.cgi',
    'intitle:"Reolink" inurl:/cgi-bin/',
    'inurl:"/Reolink" intitle:"Live" -shop -store',
    # Ubiquiti / UniFi
    'intitle:"UniFi Video" inurl:login',
    'intitle:"UniFi Protect" inurl:7443',
    'inurl:snap.jpg intext:"ubiquiti"',
    'intitle:"UniFi Protect" inurl:/protect/live',
    'inurl:/cc/view.html intext:"unifi"',
    # Blue Iris
    'intitle:"Blue Iris Login"',
    'intitle:"Blue Iris Remote View"',
    # Android IP Webcam
    'inurl:"videomgr.html"',
    'intitle:"Android IP Webcam"',
    # Generic CGI / Directory
    'inurl:"/cgi-bin/live.cgi"',
    'inurl:"/cgi-bin/stream.cgi"',
    'inurl:"/cgi-bin/snapshot.cgi"',
    'inurl:"/cgi-bin/camctrl.cgi"',
    'intitle:"Index of /DCIM"',
    'inurl:"logo.bmp" intitle:"Webcam"',
    # Broad / Catch-all
    'intitle:"Live View" inurl:"login.cgi"',
    'intitle:"IP Camera" inurl:"login.html"',
    'inurl:"/view/index.shtml" -inurl:axis',
    'inurl:"/view/view.shtml" -inurl:axis',
    'inurl:"/main.cgi?next_file=main_fs.htm"',
    # GeoVision
    'intitle:"GeoVision WebCam Server" inurl:/WebCam',
    'intitle:"GeoVision" inurl:/login.htm',
    "inurl:/geovision/ login",
    'intitle:"GeoVision MultiCam Surveillance System" live view',
    'inurl:geovision filetype:txt "password"',
    # Avigilon
    'intitle:"Avigilon Control Center" inurl:/login',
    "inurl:/avigilon/viewer",
    'intitle:"Avigilon" intext:"live video"',
    "inurl:/avigilon/webclient/",
    # Vivotek
    'intitle:"Vivotek Camera" inurl:/viewer',
    'intitle:"Vivotek" intext:"live view"',
    'intitle:"Vivotek" inurl:/cgi-bin/',
    "inurl:/vivotek/ rtsp",
    # ZoneMinder
    'intitle:"ZoneMinder" inurl:/zm/index.php',
    'intext:"ZoneMinder" inurl:view=event',
    "inurl:/zoneminder/cgi-bin/nph-zms",
    # Legacy Webcam 7 / XP Ports
    'intitle:"webcam 7" inurl::8080',
    'intitle:"webcam 7" inurl::8081',
    'intitle:"webcam 7" inurl::8000',
    'intitle:"webcamXP 5" inurl::8080',
    # Shodan-Adapted / Misc
    'product:"Hikvision IP Camera"',
    'title:"IPCam Client"',
    'http.title:"WEB VIEW" dahua',
    'intitle:"Blue Iris Login"',
    # Toshiba
    'intitle:"Toshiba Network Camera"',
    'inurl:"/user/index.html" intitle:"Toshiba"',
    'intitle:"Toshiba Network Camera" user Login',
    # Generic / Other
    'inurl:"/mjpg/video.mjpg"',
    'inurl:"/axis-cgi/mjpg"',
    'inurl:"view/index.shtml"',
    'inurl:"/view/view.shtml"',
    'inurl:"/c/version.cgi"',
    'inurl:"/cgi-bin/mjpg/video.cgi"',
    'inurl:"/cgi-bin/video.jpg"',
    'inurl:"/live/index.html"',
    'inurl:"/live/view.html"',
    'inurl:"/mjpg/video.cgi?camera"',
    'inurl:"/mjpg/video.cgi?channel"',
    'inurl:"/nph-mjpeg.cgi"',
    'inurl:"/out.jpg"',
    'inurl:"/snapshot.cgi?"',
    'inurl:"/stream/video.mjpeg"',
    'inurl:"/video.cgi"',
    'inurl:"/video.mjpg"',
    'inurl:"/view/index.shtml" intitle:"Network Camera"',
    'inurl:"CgiStart?page="',
    "inurl:camctrl.cgi",
    'intitle:"IP CAMERA Viewer"',
    'intitle:"Live View / - AXIS"',
    'intitle:"NetCam Live Image"',
    'intitle:"WJ-HD150" inurl:"/login.html"',
    'intitle:"WJ-ND200" inurl:"/login.html"',
    'intitle:"i-Catcher Console - Web Monitor"',
    'intitle:"netcam live image" (disconnected)',
    'inurl:"/gallery.html" intitle:"IP Camera"',
    'inurl:":8081" intitle:"IP Camera"',
    'inurl:":8080" intitle:"IP Camera"',
    'inurl:"/guestimage.html"',
    'inurl:"/live.htm" intext:"M-JPEG"',
    'inurl:"/monitor/bflowmo.jpg"',
    'inurl:"/multiview.htm"',
    'inurl:"/view.shtml" "Network Camera"',
    'inurl:"/viewer/live.shtml"',
    'inurl:"/webapp/live/show.html"',
    'inurl:"/webcam.html"',
    'inurl:"camera-cgi/admin/param.cgi"',
    'inurl:"cgi-bin/guestimage.html"',
    'inurl:"guestimage.html" intitle:"IP Camera"',
    'inurl:"image.jpg" intitle:"IP Camera"',
    'inurl:"index.html" intitle:"Live View / - AXIS"',
    'inurl:"live/cam.html"',
    'inurl:"live/mjpeg"',
    'inurl:"mjpg/video.mjpg" intitle:"IP Camera"',
    'inurl:"nphMotionJpeg?Resolution="',
    'inurl:"snapshot.jpg"',
    'inurl:"video.mjpg"',
    'inurl:"view/index.shtml" intitle:"Axis"',
    'inurl:"view/view.shtml" intitle:"Axis"',
    "inurl:User/General_home.htm",
    "inurl:ViewerFrame?M0de=",
    "inurl:axis-cgi/mjpg (motion-JPEG)",
    "inurl:indexFrame.shtml",
    "inurl:live/cam.html",
    "inurl:top.htm inurl:currenttime",
    "inurl:view/indexFrame.shtml",
    "inurl:view/viewer_index.shtml",
    'intitle:"IP CAMERA Viewer" intext:"setting |Client setting"',
    'intitle:"Device(" AND intext:"Network Camera" AND "language:" "AND "Password"',
    'intitle:"yawcam" inurl:":8081"',
    'intitle:"iGuard Fingerprint Security System"',
    'intitle:"Edr1680 remote viewer"',
    'intitle:"NetCam Live Image" -.edu -.gov -johnny.ihackstuff.com',
    'intitle:"INTELLINET" intitle:"IP Camera Homepage"',
    'intitle:"WEBDVR" -inurl:product -inurl:demo',
    'intitle:"Middle frame of Videoconference Management System" ext:htm',
    'intitle:"--- VIDEO WEB SERVER ---" intext:"Video Web Server" "Any time & Any where" username password',
    "intitle:HomeSeer.Web.Control | Home.Status.Events.Log",
    'intitle:"supervisioncam protocol"',
    'intitle:"active webcam page"',
    "VB Viewer inurl:/viewer/live/ja/live.html",
    "inurl:control/camerainfo",
    'inurl:"/view/view.shtml?id="',
    "allintitle:Edr1680 remote viewer",
    "allintitle:EverFocus |EDSR |EDSR400 Applet",
    "allintitle:EDR1600 login |Welcome",
    'intitle:"BlueNet Video Viewer"',
    '(intitle:(EyeSpyFX|OptiCamFX) "go to camera")|(inurl:servlet/DetectBrowser)',
    'intitle:"Veo Observer XT"',
    "inurl:shtml|pl|php|htm|asp|aspx|pDf|cfm -(intext:observer)",
    'inurl:"/view.shtml"',
    'inurl:"ViewerFrame?M0de=Refresh"',
    "liveapplet",
    "intitle:liveapplet",
    'allintitle:"Network Camera NetworkCamera" (disconnected)',
    "intitle:liveapplet inurl:LvAppl",
    'intitle:"EvoCam" inurl:"webcam.html"',
    'intitle:"Live NetSnap Cam-Server feed"',
    "intitle:start inurl:cgistart",
    "site:.viewnetcam.com -www.viewnetcam.com",
    'intitle:"IP Webcam" inurl:"/greet.html"',
    'intitle:"NetCamSC*"',
    'intitle:"NetCamXL*"',
    'intitle:"NetCamSC*" | intitle:"NetCamXL*" inurl:index.html',
    '"Camera Live Image" inurl:"guestimage.html"',
    'intitle:"webcam" inurl:login',
    'inurl:/ViewerFrame? intitle:"Network Camera NetworkCamera"',
    'intitle:NetworkCamera intext:"Pan / Tilt" inurl:ViewerFrame',
    'intitle:"IP CAMERA Viewer" intext:"setting | Client setting"',
    'intitle:"Weather Wing WS-2"',
    # Linksys
    'intitle:"Linksys Viewer - Login" -inurl:mainFrame',
    'inurl:"main.cgi?next_file=main_fs.htm"',
    # TP-Link
    'intitle:"TP-LINK IP-Camera"',
    # Other / Generic Additions
    'intitle:"netcam watcher"',
    'intitle:"Network Camera NetworkCamera"',
    'intitle:"Webcam" inurl:WebCam.htm',
    "intitle:webcamxp inurl:8080",
    'inurl:"snapshot.cgi?user="',
]

FOUND_CAMS = []
FILTER_MODE = "ALL"

# Country codes for targeted scans
COUNTRIES = {
    "ID": "Indonesia",
    "US": "United States",
    "JP": "Japan",
    "IT": "Italy",
    "DE": "Germany",
    "RU": "Russia",
    "FR": "France",
    "KR": "Korea",
    "TW": "Taiwan",
    "NO": "Norway",
    "CA": "Canada",
    "GB": "United Kingdom",
    "NL": "Netherlands",
    "SE": "Sweden",
    "ES": "Spain",
    "CH": "Switzerland",
    "AT": "Austria",
    "PL": "Poland",
    "CZ": "Czech Republic",
    "RO": "Romania",
    "BR": "Brazil",
}


class InsecamScraper:
    """Scrapes the Insecam public camera directory."""

    def build_url(self, country=None, page=1):
        if country:
            return f"{INSECAM_BASE}/bycountry/{country}/?page={page}"
        return f"{INSECAM_BASE}/byrating/?page={page}"

    def scrape_page(self, url):
        """Extract camera URLs from a single Insecam page."""
        cameras = []
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                for img in soup.find_all("img"):
                    src = img.get("src", "")
                    title = img.get("title", "")

                    # Junk domains to ignore
                    junk_terms = [
                        "static",
                        "insecam",
                        "yandex",
                        "google",
                        "facebook",
                        "twitter",
                        "instagram",
                        "tiktok",
                        "analytics",
                        "doubleclick",
                    ]

                    # Skip static assets and junk
                    if "http" in src and not any(
                        term in src.lower() for term in junk_terms
                    ):
                        brand, location = self._parse_title(title)
                        cameras.append(
                            {"url": src, "brand": brand, "location": location}
                        )
        except Exception:
            pass
        return cameras

    def _parse_title(self, title):
        """Extract brand and location from Insecam title."""
        brand, location = "IP Camera", "Unknown"
        try:
            if " in " in title:
                parts = title.split(" in ")
                location = parts[1].strip()
                if "Live camera " in parts[0]:
                    brand = parts[0].replace("Live camera ", "").strip() or "IP Camera"
        except:
            pass
        return brand, location

    def scrape(self, country=None, max_pages=5):
        """Scrape multiple pages in parallel."""
        all_cameras = []
        print(f"{Fore.CYAN}[*] Scraping Insecam ({max_pages} pages)...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            urls = [self.build_url(country, page) for page in range(1, max_pages + 1)]
            results = executor.map(self.scrape_page, urls)

            for cameras in results:
                all_cameras.extend(cameras)

        # Remove duplicates
        unique = {cam["url"]: cam for cam in all_cameras}
        print(f"{Fore.GREEN}[+] Found {len(unique)} unique feeds from Insecam")
        return list(unique.values())


class DorkEngine:
    """Multi-engine Google dorking for camera discovery."""

    def search_yahoo(self, query, limit=50):
        """Search Yahoo with stealth headers."""
        results = []
        start = 1

        while len(results) < limit:
            time.sleep(random.uniform(1.0, 2.0))

            try:
                headers = {
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml",
                    "Referer": "https://www.google.com/",
                }

                url = f"https://search.yahoo.com/search?p={query}&b={start}&pz=10"
                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code != 200:
                    break

                soup = BeautifulSoup(response.text, "html.parser")
                algo_divs = soup.find_all("div", class_="algo")

                if not algo_divs:
                    break

                for div in algo_divs:
                    link = div.find("a")
                    if link:
                        href = self._extract_yahoo_url(link.get("href", ""))
                        if href and "yahoo.com" not in href:
                            results.append(
                                {
                                    "url": href,
                                    "brand": "IP Camera",
                                    "location": "Unknown",
                                }
                            )
                            if len(results) >= limit:
                                break

                start += 10
            except:
                break

        return results

    def _extract_yahoo_url(self, raw_url):
        """Extract real URL from Yahoo redirect."""
        if "/RU=" in raw_url:
            try:
                start = raw_url.find("/RU=") + 4
                end = raw_url.find("/", start)
                if end == -1:
                    end = len(raw_url)
                return unquote(raw_url[start:end])
            except:
                pass
        return raw_url if "http" in raw_url else None

    def search_startpage(self, query, limit=50):
        """Search Startpage (Google proxy)."""
        results = []
        seen = set()

        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            response = requests.post(
                "https://www.startpage.com/sp/search",
                data={"query": query, "cat": "web", "language": "english"},
                headers=headers,
                timeout=15,
            )

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    if "http" in href and "startpage" not in href and href not in seen:
                        if "reddit" not in href and "mastodon" not in href:
                            seen.add(href)
                            results.append(
                                {
                                    "url": href,
                                    "brand": "IP Camera",
                                    "location": "Unknown",
                                }
                            )
                            if len(results) >= limit:
                                break
        except:
            pass

        return results

    def process_dork(self, dork, limit=20):
        """Run a dork through multiple engines in parallel."""
        all_results = []
        seen = set()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            yahoo_future = executor.submit(self.search_yahoo, dork, limit)
            startpage_future = executor.submit(self.search_startpage, dork, limit)

            for future in concurrent.futures.as_completed(
                [yahoo_future, startpage_future]
            ):
                try:
                    for result in future.result():
                        if result["url"] not in seen:
                            seen.add(result["url"])
                            all_results.append(result)
                except:
                    pass

        return all_results

    def scan(self, limit=20):
        """Run all dorks and stream results."""
        print(f"{Fore.CYAN}[*] Running {len(CAMERA_DORKS)} camera dorks...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_map = {
                executor.submit(self.process_dork, dork, limit): dork
                for dork in CAMERA_DORKS
            }

            for future in concurrent.futures.as_completed(future_map):
                try:
                    for result in future.result():
                        yield result
                except:
                    pass


class CameraVerifier:
    """Verify camera streams and enrich with GeoIP data."""

    def get_location(self, host):
        """Lookup geographic location for an IP/hostname."""
        try:
            response = requests.get(
                f"http://ip-api.com/json/{host}?fields=status,country,city", timeout=3
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    city = data.get("city", "Unknown")
                    country = data.get("country", "Unknown")
                    return f"{city}, {country}"
        except:
            pass
        return "Unknown"

    def verify(self, camera):
        """Check if camera is live and determine stream type."""
        url = camera["url"]

        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            response = requests.get(url, timeout=6, stream=True, headers=headers)

            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "").lower()
                server = response.headers.get("Server", "Unknown")

                # Determine camera type
                cam_type = None
                if "multipart" in content_type or "x-mixed-replace" in content_type:
                    cam_type = "LIVE STREAM (MJPEG)"
                elif "image" in content_type:
                    cam_type = "SNAPSHOT (JPEG)"
                elif "video" in content_type:
                    cam_type = "VIDEO FEED"

                if cam_type:
                    # Apply filter
                    if FILTER_MODE == "STREAM" and "STREAM" not in cam_type:
                        return None
                    if FILTER_MODE == "SNAPSHOT" and "SNAPSHOT" not in cam_type:
                        return None

                    # Get location if not already known
                    location = camera.get("location", "Unknown")
                    if location == "Unknown":
                        try:
                            host = urlparse(url).hostname
                            location = self.get_location(host)
                        except:
                            pass

                    return {
                        "url": url,
                        "status": "Live",
                        "type": cam_type,
                        "server": server,
                        "brand": camera.get("brand", "IP Camera"),
                        "location": location,
                    }
        except:
            pass

        return None


def center_text(text, width=120):
    """Center text for display."""
    # Remove color codes to calculate actual length
    clean = text
    for code in [
        Fore.RED,
        Fore.GREEN,
        Fore.CYAN,
        Fore.YELLOW,
        Fore.WHITE,
        Fore.BLUE,
        Fore.MAGENTA,
        Style.BRIGHT,
        Style.RESET_ALL,
    ]:
        clean = clean.replace(code, "")
    padding = max(0, (width - len(clean)) // 2)
    return " " * padding + text


def run_scan(country=None, pages=3, mode="DORK"):
    """Execute a scan operation."""
    import threading

    global FOUND_CAMS

    insecam = InsecamScraper()
    dorker = DorkEngine()
    verifier = CameraVerifier()

    seen_urls = set()

    print(f"\n{Style.BRIGHT}{Fore.YELLOW}" + center_text(f"=== SCANNING ({mode}) ==="))
    print()

    def verify_and_print(camera):
        if camera["url"] in seen_urls:
            return
        seen_urls.add(camera["url"])

        result = verifier.verify(camera)
        if result:
            color = Fore.GREEN if "STREAM" in result["type"] else Fore.CYAN
            # Use \r to overwrite spinner line
            print(
                f"\r{color}[+] {Fore.WHITE}{result['url']} {Fore.MAGENTA}({result['brand']} | {result['location']})"
            )
            FOUND_CAMS.append(result)

    stop_spinner = False

    def spinner():
        while not stop_spinner:
            for dots in [".  ", ".. ", "..."]:
                if stop_spinner:
                    break
                sys.stdout.write(
                    f"\r{Fore.YELLOW}[*] Still searching{dots}{Style.RESET_ALL}   "
                )
                sys.stdout.flush()
                time.sleep(0.5)

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        # Insecam scraping
        if mode in ["UNIFIED", "INSECAM"]:
            cameras = insecam.scrape(country=country, max_pages=pages)
            executor.map(verify_and_print, cameras)

        # Dorking
        if mode in ["UNIFIED", "DORK"]:
            t = threading.Thread(target=spinner)
            t.start()
            try:
                for camera in dorker.scan(limit=pages * 10):
                    executor.submit(verify_and_print, camera)
            finally:
                stop_spinner = True
                t.join()
                sys.stdout.write("\r" + " " * 50 + "\r")  # Clear spinner line

    print(f"\n{Fore.CYAN}[*] Scan complete. Found {len(FOUND_CAMS)} live cameras.")

    os.makedirs("cam_scrape", exist_ok=True)

    filename = f"cam_scrape/scan_result_{int(time.time())}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(FOUND_CAMS, f, indent=4)
    print(f"{Fore.BLUE}[*] Results saved to {filename}")


def resize_terminal(rows=40, cols=125):
    """Resize the terminal window to fit content."""
    sys.stdout.write(f"\x1b[8;{rows};{cols}t")


def main():
    """Main application entry point."""
    global FILTER_MODE

    resize_terminal()

    print(f"\n{Fore.WHITE}Commands:")
    print(f"  {Fore.CYAN}/scrape [pages]{Fore.WHITE}  - Scrape Insecam directory")
    print(f"  {Fore.CYAN}/scan [pages]{Fore.WHITE}    - Deep search with dorks")
    print(f"  {Fore.CYAN}/country [code]{Fore.WHITE}  - Set target country")
    print(f"  {Fore.CYAN}/mode [type]{Fore.WHITE}     - Filter: ALL, STREAM, SNAPSHOT")
    print(f"  {Fore.CYAN}/exit{Fore.WHITE}            - Quit")

    target_country = None

    while True:
        try:
            cmd = input(f"\n{Fore.RED}eyes-on ({FILTER_MODE})> {Fore.WHITE}").strip()
            if not cmd:
                continue

            parts = cmd.split()
            command = parts[0].lower()

            if command == "/scrape":
                pages = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 3
                run_scan(country=target_country, pages=pages, mode="INSECAM")

            elif command == "/scan":
                pages = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 3
                run_scan(country=target_country, pages=pages, mode="DORK")

            elif command == "/country":
                if len(parts) > 1:
                    code = parts[1].upper()
                    if code in COUNTRIES:
                        print(
                            f"{Fore.GREEN}[+] Target set to {code} ({COUNTRIES[code]})"
                        )
                        run_scan(country=code, pages=3, mode="INSECAM")
                    else:
                        print(f"{Fore.RED}[-] Invalid country code")
                else:
                    print(f"{Fore.YELLOW}[*] Usage: /country [CODE] (e.g. US, JP, RU)")

            elif command == "/mode":
                if len(parts) > 1:
                    mode = parts[1].upper()
                    if mode in ["ALL", "STREAM", "SNAPSHOT"]:
                        FILTER_MODE = mode
                        print(f"{Fore.GREEN}[+] Filter set to {FILTER_MODE}")
                    else:
                        print(f"{Fore.RED}[-] Invalid mode")
                else:
                    print(f"{Fore.YELLOW}[*] Current: {FILTER_MODE}")

            elif command == "/exit":
                sys.exit(0)

            elif command == "/clear":
                print("\033[H\033[J", end="")

        except KeyboardInterrupt:
            print(f"\n{Fore.RED}Aborted.")
            break
        except Exception as e:
            print(f"{Fore.RED}[-] Error: {e}")


if __name__ == "__main__":
    main()
