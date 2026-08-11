"""Single-password auth via signed cookie. If APP_PASSWORD is unset, auth is off."""
import hashlib
import hmac
import os

from fastapi import Request

COOKIE_NAME = "yhc_session"


def _password() -> str:
    return os.environ.get("APP_PASSWORD", "")


def _secret() -> bytes:
    # Derive a stable secret from the password so cookies survive restart.
    return hashlib.sha256(("yhc::" + _password()).encode()).digest()


def enabled() -> bool:
    return bool(_password())


def make_token() -> str:
    return hmac.new(_secret(), b"ok", hashlib.sha256).hexdigest()


def check_password(password: str) -> bool:
    return hmac.compare_digest(password, _password())


def is_authed(request: Request) -> bool:
    if not enabled():
        return True
    token = request.cookies.get(COOKIE_NAME, "")
    return hmac.compare_digest(token, make_token())
