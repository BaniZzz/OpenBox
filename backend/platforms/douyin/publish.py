"""Build the H5 share schema the Douyin app consumes when a person scans it.

`snssdk1128://openplatform/share?share_type=h5&…` — the app downloads the
video from `video_path` itself, so the only thing the backend ships is a
short-lived signed URL plus the signature over (nonce_str, ticket, timestamp).
"""
import json
from urllib.parse import urlencode

from platforms.douyin.client import DouyinClient

SCHEMA_BASE = "snssdk1128://openplatform/share"
#: Documented ceiling for a single video in the H5 flow.
MAX_VIDEO_BYTES = 128 * 1024 * 1024
ALLOWED_VIDEO_MIMES = {"video/mp4", "video/quicktime", "video/3gpp"}


def build_share_schema(
    *,
    client_key: str,
    ticket: str,
    video_url: str,
    share_id: str | None,
    title: str = "",
    hashtags: list[str] | None = None,
    private_status: int = 0,
    download_type: int = 1,
    nonce_str: str | None = None,
    timestamp: str | None = None,
) -> str:
    nonce = nonce_str or DouyinClient.new_nonce()
    ts = timestamp or DouyinClient.now_timestamp()
    params: dict[str, str] = {
        "share_type": "h5",
        "client_key": client_key,
        "nonce_str": nonce,
        "timestamp": ts,
        "signature": DouyinClient.sign_share(ticket, nonce, ts),
        "video_path": video_url,
        # Straight to the publish page; the person still presses 发布 there.
        "share_to_publish": "1",
        "share_to_type": "0",
        "private_status": str(int(private_status)),
        "download_type": str(int(download_type)),
    }
    if share_id:
        params["state"] = share_id
    if title:
        params["title"] = title[:55]
    tags = [t.strip().lstrip("#") for t in (hashtags or []) if t and t.strip().lstrip("#")]
    if tags:
        params["hashtag_list"] = json.dumps(tags[:10], ensure_ascii=False)
    return f"{SCHEMA_BASE}?{urlencode(params)}"
