"""Versleutelde opslag van mailboxgegevens (wachtwoorden en tokens staan nooit leesbaar op schijf)."""
import base64, hashlib, json, os, threading
from cryptography.fernet import Fernet

DATA_DIR = os.environ.get("DATA_DIR", "./data")
_PATH = os.path.join(DATA_DIR, "mailboxen.enc")
_lock = threading.Lock()


def _fernet() -> Fernet:
    raw = os.environ.get("DATA_KEY", "")
    if len(raw) < 16:
        raise RuntimeError("DATA_KEY ontbreekt of is te kort")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()))


def load() -> dict:
    with _lock:
        if not os.path.exists(_PATH):
            return {}
        with open(_PATH, "rb") as f:
            return json.loads(_fernet().decrypt(f.read()))


def save(data: dict) -> None:
    with _lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = _PATH + ".tmp"
        with open(tmp, "wb") as f:
            f.write(_fernet().encrypt(json.dumps(data).encode()))
        os.replace(tmp, _PATH)


def update(key: str, fields: dict) -> None:
    data = load()
    data.setdefault(key, {}).update(fields)
    save(data)


def remove(key: str) -> None:
    data = load()
    data.pop(key, None)
    save(data)
