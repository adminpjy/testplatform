import base64
import hashlib
import os

from app.core.config import settings


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    nonce = os.urandom(16)
    key = _key_stream(nonce, len(value.encode("utf-8")))
    payload = bytes(byte ^ key[index] for index, byte in enumerate(value.encode("utf-8")))
    return "v1:" + base64.urlsafe_b64encode(nonce + payload).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    if not value.startswith("v1:"):
        return None
    raw = base64.urlsafe_b64decode(value[3:].encode("ascii"))
    nonce, payload = raw[:16], raw[16:]
    key = _key_stream(nonce, len(payload))
    clear = bytes(byte ^ key[index] for index, byte in enumerate(payload))
    return clear.decode("utf-8")


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    return "***REDACTED***"


def _key_stream(nonce: bytes, length: int) -> bytes:
    secret = settings.local_secret_key.get_secret_value().encode("utf-8")
    chunks: list[bytes] = []
    counter = 0
    while sum(len(chunk) for chunk in chunks) < length:
        chunks.append(hashlib.sha256(secret + nonce + counter.to_bytes(4, "big")).digest())
        counter += 1
    return b"".join(chunks)[:length]
