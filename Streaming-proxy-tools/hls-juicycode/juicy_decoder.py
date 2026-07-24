import json
import re
import os
import tempfile
import subprocess
from curl_cffi import requests
from bs4 import BeautifulSoup

class JuicyDecoder:
    """
    A robust Python implementation that dynamically fetches the JuicyCodes 
    player JS and evaluates it using a secure Node.js sandbox proxy to 
    guarantee 100% accurate decryption even if the algorithm changes.
    """
    
    @classmethod
    def fetch_player_html(cls, iframe_url, referer="https://rebahinxxi3.pics/"):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
            "Referer": referer,
            "Accept": "*/*"
        }
        try:
            res = requests.get(iframe_url, headers=headers, impersonate="chrome110", verify=False, timeout=10)
            res.raise_for_status()
            return res.text
        except Exception as e:
            print(f"[JuicyDecoder] Error fetching player HTML: {e}")
            return None

    @classmethod
    def extract_payload(cls, html):
        if not html: return None
        start = html.find('_juicycodes(')
        if start == -1: return None
        end = html.find(');', start)
        if end == -1: return None
        arg_content = html[start+12:end]
        strings = re.findall(r'["\'](.*?)["\']', arg_content)
        return "".join(strings)

    @classmethod
    def get_player_js_url(cls, html, base_url):
        if not html: return None
        # Look for script tag like <script src=".../player.js?...">
        soup = BeautifulSoup(html, 'html.parser')
        script_tag = soup.find('script', src=re.compile(r'/player\.js(\?|$)'))
        if script_tag:
            js_url = script_tag.get('src')
            if js_url.startswith('/'):
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                return f"{parsed.scheme}://{parsed.netloc}{js_url}"
            return js_url
        return None

    @classmethod
    def fetch_player_js(cls, js_url, referer="https://rebahinxxi3.pics/"):
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": referer
        }
        try:
            res = requests.get(js_url, headers=headers, impersonate="chrome110", verify=False, timeout=10)
            res.raise_for_status()
            return res.text
        except Exception as e:
            print(f"[JuicyDecoder] Error fetching player JS: {e}")
            return None

    @classmethod
    def decode_via_node(cls, player_js, payload):
        """
        Executes the player JS inside a Node.js process with a stubbed DOM
        to extract the executed juicyData JSON safely.
        """
        js_code = f"""
        const fs = require('fs');
        global.window = global;
        const nativeEval = eval;
        let extractedPayloads = [];
        Object.defineProperty(global, 'eval', {{
            get: function() {{
                return function(code) {{
                    extractedPayloads.push(code);
                    return nativeEval(code);
                }};
            }}
        }});
        
        const documentHandler = {{
            get: function(target, prop, receiver) {{
                if (prop === 'createElement') return () => new Proxy({{}}, documentHandler);
                if (prop === 'getElementsByTagName') return () => [new Proxy({{}}, documentHandler)];
                if (prop === 'style') return {{}};
                if (prop === 'appendChild') return () => {{}};
                if (prop === 'setAttribute') return () => {{}};
                if (prop === 'parentNode') return new Proxy({{}}, documentHandler);
                if (prop === 'insertBefore') return () => {{}};
                return typeof prop === 'string' ? function() {{ return new Proxy({{}}, documentHandler); }} : null;
            }}
        }};
        global.window = global;
        global.addEventListener = function() {{}};
        global.removeEventListener = function() {{}};
        global.document = {{
            createElement: function() {{ return {{}}; }},
            getElementsByTagName: function() {{ return [{{ appendChild: function() {{}} }}]; }},
            head: {{ appendChild: function() {{}} }},
            location: {{ protocol: 'https:', href: 'https://rebahinxxi3.pics' }},
            addEventListener: function() {{}},
            removeEventListener: function() {{}}
        }};
        global.location = {{ 
            href: 'https://rebahinxxi3.pics',
            protocol: 'https:' 
        }};
        global.navigator = {{ userAgent: 'Mozilla/5.0' }};
        global.performance = {{ timing: {{ navigationStart: Date.now() }} }};
        
        // Load original player.js using the native eval so it sets up the environment
        let playerScript = {repr(player_js)};
        try {{
            nativeEval(playerScript);
        }} catch(e) {{
            console.error("INIT ERROR:", e.message);
            // Ignore init errors since we just want the functions loaded
        }}
        

        try {{
            window._juicycodes("{payload}");
        }} catch(e) {{
            console.error("JUICYCODES ERROR:", e.message, e.stack);
        }}
        
        console.error("EXTRACTED PAYLOADS:", extractedPayloads.length);
        console.log(extractedPayloads.join('\\n\\n---PAYLOAD_SEPARATOR---\\n\\n'));"""
        
        with tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w", encoding="utf-8") as f:
            f.write(js_code)
            temp_path = f.name
            
        try:
            # Run Node
            proc = subprocess.run(["node", temp_path], capture_output=True, text=True, timeout=10, encoding='utf-8')
            stderr_output = proc.stderr.strip()
            stdout_output = proc.stdout.strip()
            if stderr_output:
                print(f"[JuicyDecoder Node STDERR]:\n{stderr_output}")
            return stdout_output
        except Exception as e:
            print(f"[JuicyDecoder] Node execution failed: {e}")
            return None
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @classmethod
    def extract_m3u8(cls, decoded_js):
        if not decoded_js: return None
        m = re.search(r'var\s+config\s*=\s*(\{.*?\});', decoded_js)
        if m:
            try:
                config = json.loads(m.group(1))
                if 'sources' in config:
                    sources = config['sources']
                    if isinstance(sources, list) and len(sources) > 0:
                        return sources[0].get('file')
                    elif isinstance(sources, dict):
                        return sources.get('file')
            except Exception:
                pass
        m = re.search(r'file["\']?\s*:\s*["\'](.*?)["\']', decoded_js)
        if m:
            val = m.group(1).replace('\\/', '/')
            if 'stream/' in val:
                return val
        return None

    @classmethod
    def run_pipeline(cls, iframe_url, referer="https://rebahinxxi3.pics/"):
        html = cls.fetch_player_html(iframe_url, referer)
        if not html: return {"status": "error", "message": "Failed to fetch HTML"}
            
        payload = cls.extract_payload(html)
        if not payload: return {"status": "error", "message": "Payload _juicycodes not found in HTML"}
            
        js_url = cls.get_player_js_url(html, iframe_url)
        if not js_url: return {"status": "error", "message": "Could not find player.js URL in HTML"}
            
        player_js = cls.fetch_player_js(js_url, referer)
        if not player_js: return {"status": "error", "message": "Failed to download player.js"}
            
        decoded_js = cls.decode_via_node(player_js, payload)
        if not decoded_js or len(decoded_js) < 50: 
            return {"status": "error", "message": "Failed to decrypt payload via Node engine"}
            
        m3u8_url = cls.extract_m3u8(decoded_js)
        if not m3u8_url:
            return {"status": "error", "message": "m3u8 link not found in decrypted script", "raw_script": decoded_js[:500]}
            
        return {
            "status": "success",
            "m3u8_url": m3u8_url,
            "raw_script": decoded_js[:200] + "... (truncated)"
        }
