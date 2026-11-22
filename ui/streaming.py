"""HTTP Range (206) file streaming for the in-page player, and attachment downloads."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from fastapi.responses import Response, StreamingResponse

CHUNK = 1 << 20


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """'bytes=START-END' -> inclusive (start, end). None = whole file. Raises ValueError when unsatisfiable."""
    if not header:
        return None
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if not m or (not m.group(1) and not m.group(2)):
        raise ValueError("bad range")
    if m.group(1):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
    else:  # suffix range: the last N bytes
        n = int(m.group(2))
        start, end = max(0, size - n), size - 1
    end = min(end, size - 1)
    if start >= size or start > end:
        raise ValueError("unsatisfiable")
    return start, end


def _iter(path: Path, start: int, end: int) -> Iterator[bytes]:
    with path.open("rb") as fh:
        fh.seek(start)
        left = end - start + 1
        while left > 0:
            data = fh.read(min(CHUNK, left))
            if not data:
                break
            left -= len(data)
            yield data


def stream_file(path: Path, request: Request, media_type: str = "video/mp4") -> Response:
    size = path.stat().st_size
    base = {"Accept-Ranges": "bytes", "Cache-Control": "no-store"}
    try:
        rng = parse_range(request.headers.get("range"), size)
    except ValueError:
        return Response(status_code=416, headers={**base, "Content-Range": f"bytes */{size}"})
    if rng is None:
        return StreamingResponse(
            _iter(path, 0, size - 1), media_type=media_type, headers={**base, "Content-Length": str(size)}
        )
    start, end = rng
    return StreamingResponse(
        _iter(path, start, end),
        status_code=206,
        media_type=media_type,
        headers={**base, "Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(end - start + 1)},
    )


def download_file(path: Path, filename: str, media_type: str = "video/mp4") -> Response:
    safe = re.sub(r"[^\w.\- ]+", "_", filename)
    return StreamingResponse(
        _iter(path, 0, path.stat().st_size - 1),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe}"', "Content-Length": str(path.stat().st_size)},
    )
