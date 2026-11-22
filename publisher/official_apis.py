"""Official platform APIs (optional; the browser-cookie method stays the default).

Audit caveats, shown in the UI too:
  - YouTube Data API v3: uploads from an unverified Google Cloud project are locked to PRIVATE
    until the project passes Google's API audit. Default quota allows roughly 6 uploads/day.
  - Instagram Graph API: needs a Business/Creator account linked to a Facebook Page and a Meta app
    with Facebook Login for Business. Uses the resumable Reels upload (local file, no hosting needed).
  - TikTok Content Posting API: unaudited apps can only post SELF_ONLY (private).

Credentials: YouTube OAuth client file at config/secrets/youtube_client_secret.json, token saved
next to it after "Connect YouTube API". Instagram/TikTok tokens come from .env (Settings tab).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests

from common import settings

YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YT_CLIENT = settings.SECRETS_DIR / "youtube_client_secret.json"
YT_TOKEN = settings.SECRETS_DIR / "youtube_token.json"


class ApiNotConfigured(RuntimeError):
    pass


# ------------------------------------------------------------------ YouTube
def youtube_connect() -> str:
    """One-time OAuth consent in the browser; stores a refreshable token locally."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    cid, secret = settings.env("YOUTUBE_CLIENT_ID"), settings.env("YOUTUBE_CLIENT_SECRET")
    if YT_CLIENT.exists():
        flow = InstalledAppFlow.from_client_secrets_file(str(YT_CLIENT), YT_SCOPES)
    elif cid and secret:  # Client ID + secret typed into Settings instead of uploading client_secret.json
        config = {
            "installed": {
                "client_id": cid,
                "client_secret": secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(config, YT_SCOPES)
    else:
        raise ApiNotConfigured(
            "Upload client_secret.json (Desktop app) or enter the Client ID and Client Secret in Settings. "
            "Google Cloud Console > APIs & Services > Credentials > Create OAuth client ID > Desktop."
        )
    creds = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True)
    YT_TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return "YouTube API connected"


def _youtube_creds():  # type: ignore[no-untyped-def]
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not YT_TOKEN.exists():
        raise ApiNotConfigured("YouTube API not connected. Settings > Publishing > Connect YouTube API.")
    creds = Credentials.from_authorized_user_file(str(YT_TOKEN), YT_SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        YT_TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return creds


def youtube_upload(video: Path, meta: dict[str, Any], visibility: str, thumbnail: Path | None = None) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    yt = build("youtube", "v3", credentials=_youtube_creds(), cache_discovery=False)
    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta.get("full_description", meta.get("description", ""))[:5000],
            "tags": meta.get("tags", [])[:30],
            "categoryId": str(meta.get("category_id", "27")),  # 27 = Education
        },
        "status": {"privacyStatus": visibility, "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(
        part="snippet,status", body=body, media_body=MediaFileUpload(str(video), chunksize=8 << 20, resumable=True)
    )
    resp = None
    while resp is None:
        _status, resp = req.next_chunk()
    vid = resp["id"]
    if thumbnail and thumbnail.exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumbnail))).execute()
        except Exception as exc:  # noqa: BLE001 - custom thumbnails need a verified channel; upload still succeeded
            print(f"thumbnail not set: {exc}")
    return f"https://youtu.be/{vid}"


# ------------------------------------------------------------------ Instagram (Graph API, Reels)
def instagram_upload(video: Path, caption: str, cover_offset_ms: int = 0) -> str:
    token, user = settings.env("INSTAGRAM_ACCESS_TOKEN"), settings.env("INSTAGRAM_USER_ID")
    if not token or not user:
        raise ApiNotConfigured("Set INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_USER_ID in Settings.")
    ver = settings.load()["publish"]["graph_api_version"]
    auth = {"Authorization": f"Bearer {token}"}
    init = requests.post(
        f"https://graph.facebook.com/{ver}/{user}/media",
        headers=auth,
        json={
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption[:2200],
            "thumb_offset": cover_offset_ms,
        },
        timeout=60,
    )
    if not init.ok:
        raise RuntimeError(f"Instagram container failed: {init.status_code} {init.text[:300]}")
    container, uri = init.json()["id"], init.json()["uri"]
    size = video.stat().st_size
    with video.open("rb") as fh:
        up = requests.post(
            uri,
            headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)},
            data=fh,
            timeout=600,
        )
    if not up.ok:
        raise RuntimeError(f"Instagram upload failed: {up.status_code} {up.text[:300]}")
    for _ in range(60):  # processing usually takes 10-60 s
        st = requests.get(
            f"https://graph.facebook.com/{ver}/{container}",
            params={"fields": "status_code,status"},
            headers=auth,
            timeout=30,
        ).json()
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing failed: {st}")
        time.sleep(5)
    pub = requests.post(
        f"https://graph.facebook.com/{ver}/{user}/media_publish",
        headers=auth,
        params={"creation_id": container},
        timeout=60,
    )
    if not pub.ok:
        raise RuntimeError(f"Instagram publish failed: {pub.status_code} {pub.text[:300]}")
    return f"instagram media {pub.json().get('id')}"


# ------------------------------------------------------------------ TikTok (Content Posting API, Direct Post)
def tiktok_upload(video: Path, title: str, privacy_level: str = "SELF_ONLY") -> str:
    """Single-chunk FILE_UPLOAD (files up to 64 MB). Unaudited apps must use SELF_ONLY."""
    token = settings.env("TIKTOK_ACCESS_TOKEN")
    if not token:
        raise ApiNotConfigured("Set TIKTOK_ACCESS_TOKEN in Settings.")
    size = video.stat().st_size
    if size > 64 * 1024 * 1024:
        raise RuntimeError("TikTok single-chunk upload supports files up to 64 MB")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    init = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers=headers,
        json={
            "post_info": {"title": title[:2200], "privacy_level": privacy_level, "video_cover_timestamp_ms": 0},
            "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1},
        },
        timeout=60,
    )
    data = init.json()
    if not init.ok or data.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok init failed: {init.status_code} {str(data)[:300]}")
    upload_url, publish_id = data["data"]["upload_url"], data["data"]["publish_id"]
    with video.open("rb") as fh:
        put = requests.put(
            upload_url,
            headers={
                "Content-Range": f"bytes 0-{size - 1}/{size}",
                "Content-Type": "video/mp4",
                "Content-Length": str(size),
            },
            data=fh,
            timeout=600,
        )
    if put.status_code not in (200, 201):
        raise RuntimeError(f"TikTok upload failed: {put.status_code} {put.text[:300]}")
    for _ in range(40):
        st = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
            headers=headers,
            json={"publish_id": publish_id},
            timeout=30,
        ).json()
        status = st.get("data", {}).get("status")
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            return f"tiktok {publish_id} {status}"
        if status == "FAILED":
            raise RuntimeError(f"TikTok publish failed: {st}")
        time.sleep(5)
    return f"tiktok {publish_id} processing"


def status() -> dict[str, Any]:
    """What is configured, for the Settings page (no secrets)."""
    return {
        "youtube": {
            "client_file": YT_CLIENT.exists() or bool(settings.env("YOUTUBE_CLIENT_ID")),
            "connected": YT_TOKEN.exists(),
        },
        "instagram": {
            "token": bool(settings.env("INSTAGRAM_ACCESS_TOKEN")),
            "user_id": bool(settings.env("INSTAGRAM_USER_ID")),
        },
        "tiktok": {"token": bool(settings.env("TIKTOK_ACCESS_TOKEN"))},
    }


def configured(platform: str) -> bool:
    """True when the official-API credentials for a platform are all present."""
    s = status()[platform]
    return all(s.values()) if platform == "instagram" else bool(s.get("connected") or s.get("token"))


def test_connection(platform: str) -> str:
    """One cheap authenticated read per platform. Returns a sentence for the UI log; raises with the reason."""
    if platform == "youtube":
        from googleapiclient.discovery import build

        yt = build("youtube", "v3", credentials=_youtube_creds(), cache_discovery=False)
        items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
        return (
            f"YouTube API OK: channel {items[0]['snippet']['title']!r}"
            if items
            else "YouTube API OK (no channel on this account)"
        )
    if platform == "instagram":
        token, user = settings.env("INSTAGRAM_ACCESS_TOKEN"), settings.env("INSTAGRAM_USER_ID")
        if not token or not user:
            raise ApiNotConfigured("Set the Instagram user ID and access token first.")
        ver = settings.load()["publish"]["graph_api_version"]
        r = requests.get(
            f"https://graph.facebook.com/{ver}/{user}",
            params={"fields": "username"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if not r.ok:
            raise RuntimeError(f"Instagram answered HTTP {r.status_code}: {r.text[:160]}")
        return f"Instagram API OK: @{r.json().get('username', '?')}"
    if platform == "tiktok":
        token = settings.env("TIKTOK_ACCESS_TOKEN")
        if not token:
            raise ApiNotConfigured("Set the TikTok access token first.")
        r = requests.get(
            "https://open.tiktokapis.com/v2/user/info/",
            params={"fields": "open_id,display_name"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if not r.ok:
            raise RuntimeError(f"TikTok answered HTTP {r.status_code}: {r.text[:160]}")
        return f"TikTok API OK: {r.json().get('data', {}).get('user', {}).get('display_name', 'account')}"
    raise ValueError(f"unknown platform {platform}")
