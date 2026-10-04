"""Input sanitising, logo validation and a tiny in-memory rate limiter.

Nothing here (or anywhere in LegalEase) writes user data to disk or logs it.
"""
import base64
import binascii
import io
import re
import threading
import time
from collections import defaultdict, deque

from PIL import Image

from .config import MAX_FIELD_LEN, MAX_LOGO_BYTES

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_DATA_URL = re.compile(r"^data:image/(png|jpeg|jpg);base64,(.+)$", re.DOTALL)


def clean_text(value: str, multiline: bool = False) -> str:
    value = _CTRL.sub("", str(value)).strip()[:MAX_FIELD_LEN]
    return value if multiline else re.sub(r"\s+", " ", value)


def process_logo(data_url):
    """Validate an uploaded logo and return (png_bytes, width_px, height_px).

    The image is fully decoded and re-encoded as PNG, which strips metadata and
    rejects anything that is not a real PNG/JPEG.
    """
    if not data_url:
        return None
    m = _DATA_URL.match(data_url.strip())
    if not m:
        raise ValueError("Logo must be a PNG or JPEG image.")
    try:
        raw = base64.b64decode(m.group(2), validate=False)
    except (binascii.Error, ValueError):
        raise ValueError("Logo data is not valid base64.")
    if len(raw) > MAX_LOGO_BYTES:
        raise ValueError("Logo is too large (max 2 MB).")
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ("PNG", "JPEG"):
            raise ValueError
        img.load()
    except Exception:
        raise ValueError("Logo is not a valid PNG or JPEG image.")
    if img.width * img.height > 25_000_000:
        raise ValueError("Logo dimensions are too large.")
    img.thumbnail((800, 800))                       # keep exports light
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue(), img.width, img.height


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True
