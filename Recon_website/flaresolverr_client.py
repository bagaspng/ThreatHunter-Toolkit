import time
import requests
FLARESOLVERR_URL = 'http://localhost:8191/v1'
DEFAULT_TIMEOUT_MS = 60000

def fetch_via_flaresolverr(url, log_fn, session_id=None, timeout_ms=DEFAULT_TIMEOUT_MS):
    payload = {'cmd': 'request.get', 'url': url, 'maxTimeout': timeout_ms}
    if session_id:
        payload['session'] = session_id
    try:
        resp = requests.post(FLARESOLVERR_URL, json=payload, timeout=timeout_ms / 1000 + 5)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.ConnectionError:
        return (None, None, None, {}, 'FlareSolverr tidak bisa diakses. Pastikan container jalan: docker ps | grep flaresolverr')
    except Exception as e:
        return (None, None, None, {}, f'Request ke FlareSolverr gagal: {e}')
    if data.get('status') != 'ok':
        return (None, None, None, {}, data.get('message', 'FlareSolverr mengembalikan status error tanpa pesan.'))
    solution = data.get('solution', {})
    html = solution.get('response')
    cookies = solution.get('cookies', [])
    user_agent = solution.get('userAgent')
    headers = solution.get('headers', {}) or {}
    if not html:
        return (None, None, None, {}, 'FlareSolverr sukses tapi response HTML kosong.')
    log_fn(f'  [+] FlareSolverr berhasil, status challenge: {solution.get('status')}, UA dipakai: {user_agent}')
    return (html, cookies, user_agent, headers, None)

def fetch_via_flaresolverr_with_retry(url, log_fn, is_still_challenge_fn, session_id=None, attempts=3, timeout_ms_list=None):
    if timeout_ms_list is None:
        timeout_ms_list = [DEFAULT_TIMEOUT_MS, 90000, 120000]
    last_err = None
    for i in range(attempts):
        timeout_ms = timeout_ms_list[min(i, len(timeout_ms_list) - 1)]
        if i > 0:
            log_fn(f'  [*] Percobaan FlareSolverr ke-{i + 1}/{attempts} (maxTimeout={timeout_ms}ms)...')
            time.sleep(2)
        html, cookies, user_agent, headers, err = fetch_via_flaresolverr(url, log_fn, session_id=session_id, timeout_ms=timeout_ms)
        if err:
            last_err = err
            continue
        if is_still_challenge_fn(html):
            last_err = 'HTML hasil masih challenge page setelah FlareSolverr melapor sukses'
            log_fn(f'  [!] Percobaan {i + 1}/{attempts}: {last_err}, coba lagi...')
            continue
        return (html, cookies, user_agent, headers, None)
    return (None, None, None, {}, last_err or 'Semua percobaan FlareSolverr gagal.')

def create_flaresolverr_session(log_fn, session_id='recon_session'):
    payload = {'cmd': 'sessions.create', 'session': session_id}
    try:
        resp = requests.post(FLARESOLVERR_URL, json=payload, timeout=15)
        data = resp.json()
        if data.get('status') == 'ok':
            log_fn(f"  [i] FlareSolverr session '{session_id}' dibuat.")
            return session_id
        log_fn(f'  [!] Gagal bikin FlareSolverr session: {data.get('message')}')
        return None
    except Exception as e:
        log_fn(f'  [!] Gagal konek ke FlareSolverr untuk bikin session (lanjut tanpa session): {e}')
        return None

def destroy_flaresolverr_session(log_fn, session_id='recon_session'):
    if not session_id:
        return
    payload = {'cmd': 'sessions.destroy', 'session': session_id}
    try:
        requests.post(FLARESOLVERR_URL, json=payload, timeout=15)
        log_fn(f"  [i] FlareSolverr session '{session_id}' ditutup.")
    except Exception:
        pass

def cookies_list_to_requests_dict(cookies_list):
    return {c['name']: c['value'] for c in cookies_list} if cookies_list else {}