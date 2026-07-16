import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone

HMAC_ALGS = {"HS256": hashlib.sha256, "HS384": hashlib.sha384,
             "HS512": hashlib.sha512}

CLAIM_NAMES = {
    "iss": "Issuer", "sub": "Subject", "aud": "Audience",
    "exp": "Expiration Time", "nbf": "Not Before", "iat": "Issued At",
    "jti": "JWT ID",
}
TIME_CLAIMS = ("exp", "nbf", "iat")


def b64url_decode(seg):
    if isinstance(seg, str):
        seg = seg.encode("ascii")
    pad = (-len(seg)) % 4
    return base64.urlsafe_b64decode(seg + b"=" * pad)


def b64url_encode(raw):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _fmt_time(ts):
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _claim_note(name, value):
    if name in TIME_CLAIMS and isinstance(value, (int, float)):
        human = _fmt_time(value)
        if human is None:
            return None
        now = datetime.now(tz=timezone.utc).timestamp()
        if name == "exp":
            status = "sudah kedaluwarsa" if value < now else "masih berlaku"
            return "%s (%s)" % (human, status)
        if name == "nbf":
            status = "sudah aktif" if value <= now else "belum aktif"
            return "%s (%s)" % (human, status)
        return human
    return None


def describe_claims(payload):
    out = []
    if not isinstance(payload, dict):
        return out
    for key, value in payload.items():
        label = CLAIM_NAMES.get(key)
        note = _claim_note(key, value)
        if label or note:
            out.append({"key": key, "label": label or key,
                        "value": value, "note": note})
    return out


def decode(token):
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("Token JWT harus terdiri dari 3 bagian "
                         "dipisah titik (header.payload.signature).")
    h_seg, p_seg, s_seg = parts
    try:
        header = json.loads(b64url_decode(h_seg))
    except Exception:
        raise ValueError("Header bukan base64url JSON yang valid.")
    try:
        payload = json.loads(b64url_decode(p_seg))
    except Exception:
        raise ValueError("Payload bukan base64url JSON yang valid.")
    algorithm = header.get("alg") if isinstance(header, dict) else None
    return {
        "header": header,
        "payload": payload,
        "signature": s_seg,
        "algorithm": algorithm,
        "signing_input": h_seg + "." + p_seg,
        "claims": describe_claims(payload),
    }


def _sign(signing_input, secret, algorithm):
    func = HMAC_ALGS.get(algorithm)
    if func is None:
        raise ValueError("Algoritma %r tidak didukung (hanya HS256/HS384/HS512)."
                         % algorithm)
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    if isinstance(signing_input, str):
        signing_input = signing_input.encode("ascii")
    return hmac.new(secret, signing_input, func).digest()


def verify(token, secret):
    info = decode(token)
    algorithm = info["algorithm"]
    if algorithm not in HMAC_ALGS:
        return {"verified": False, "algorithm": algorithm,
                "reason": "Verifikasi hanya untuk HMAC (HS256/384/512); "
                          "algoritma %r butuh kunci publik/privat." % algorithm}
    expected = _sign(info["signing_input"], secret, algorithm)
    try:
        got = b64url_decode(info["signature"])
    except Exception:
        return {"verified": False, "algorithm": algorithm,
                "reason": "Signature pada token bukan base64url yang valid."}
    ok = hmac.compare_digest(expected, got)
    return {"verified": ok, "algorithm": algorithm,
            "reason": "Signature cocok dengan secret." if ok
                      else "Signature tidak cocok dengan secret."}


def encode(payload, secret, algorithm="HS256", header=None):
    if algorithm not in HMAC_ALGS:
        raise ValueError("Algoritma %r tidak didukung (hanya HS256/HS384/HS512)."
                         % algorithm)
    head = {"alg": algorithm, "typ": "JWT"}
    if header:
        head.update(header)
        head["alg"] = algorithm
    h_seg = b64url_encode(json.dumps(head, separators=(",", ":"),
                                     ensure_ascii=False))
    p_seg = b64url_encode(json.dumps(payload, separators=(",", ":"),
                                     ensure_ascii=False))
    signing_input = h_seg + "." + p_seg
    s_seg = b64url_encode(_sign(signing_input, secret, algorithm))
    return signing_input + "." + s_seg
