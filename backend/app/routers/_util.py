"""HTTP helpers shared by routers: file downloads and byte-range (video) responses."""

from __future__ import annotations

import re
import unicodedata
from collections import OrderedDict
from urllib.parse import quote

from fastapi import Response


def download_response(data: bytes, filename: str, media_type: str) -> Response:
    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"[^\w\s.\-]", "", ascii_name).strip() or "studyforge"
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    return Response(data, media_type=media_type, headers={"Content-Disposition": disposition, "Cache-Control": "no-store"})


def range_response(data: bytes, range_header: str | None, media_type: str, etag: str) -> Response:
    """Serve bytes with HTTP Range support so browsers can seek within videos."""
    size = len(data)
    headers = {"Accept-Ranges": "bytes", "ETag": etag, "Cache-Control": "public, max-age=3600"}
    if not range_header:
        return Response(data, media_type=media_type, headers={**headers, "Content-Length": str(size)})

    m = re.match(r"bytes=(\d*)-(\d*)$", range_header.strip())
    if not m or (not m.group(1) and not m.group(2)):
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    if m.group(1):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
    else:  # suffix range: last N bytes
        start = max(size - int(m.group(2)), 0)
        end = size - 1
    end = min(end, size - 1)
    if start > end or start >= size:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    chunk = data[start : end + 1]
    return Response(
        chunk,
        status_code=206,
        media_type=media_type,
        headers={**headers, "Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(len(chunk))},
    )


class BytesLRU:
    """Tiny in-memory cache so video seeking doesn't reload the blob from the DB each time."""

    def __init__(self, max_items: int = 6):
        self.max_items = max_items
        self._items: OrderedDict[str, bytes] = OrderedDict()

    def get(self, key: str) -> bytes | None:
        if key in self._items:
            self._items.move_to_end(key)
            return self._items[key]
        return None

    def put(self, key: str, value: bytes) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self.max_items:
            self._items.popitem(last=False)
