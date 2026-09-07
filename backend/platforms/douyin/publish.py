"""Build the H5 share schema the Douyin app consumes when a person scans it.

`snssdk1128://openplatform/share?share_type=h5&…` — the app downloads the
video from `video_path` itself, so the only thing the backend ships is a
short-lived signed URL plus the signature over (nonce_str, ticket, timestamp).

Encoding follows Douyin's own `dy_open_util.serialize` byte for byte: keys
sorted, every key and value run through `encodeURIComponent` semantics
(space → %20, never `+`), unknown/empty values dropped. Hashtags are sent
twice on purpose: `hashtag_list` pre-fills the topic chips on the publish
page, `title_hashtag_list` writes them into the caption itself so they
survive even when the chips are not shown.
"""
import json
from urllib.parse import quote

from platforms.douyin.client import DouyinClient

SCHEMA_BASE = "snssdk1128://openplatform/share"
#: Documented ceiling for a single video in the H5 flow.
MAX_VIDEO_BYTES = 128 * 1024 * 1024
ALLOWED_VIDEO_MIMES = {"video/mp4", "video/quicktime", "video/3gpp"}
#: Douyin caps the caption; keep room for the inline hashtags.
MAX_TITLE_CHARS = 55
MAX_HASHTAGS = 10

#: Characters encodeURIComponent leaves alone (RFC 3986 unreserved + !'()*).
_JS_SAFE = "-_.!~*'()"


def js_encode(value: str) -> str:
    return quote(value, safe=_JS_SAFE)


def clean_hashtags(hashtags: list[str] | None) -> list[str]:
    out: list[str] = []
    for tag in hashtags or []:
        t = (tag or "").strip().lstrip("#").strip()
        if t and t not in out:
            out.append(t)
    return out[:MAX_HASHTAGS]


def serialize_share(params: dict[str, str | None]) -> str:
    """Same wire format as dy_open_util.serialize: sorted, JS-encoded, no blanks."""
    query = "&".join(
        f"{js_encode(k)}={js_encode(v)}"
        for k, v in sorted(params.items())
        if v is not None and v != ""
    )
    return f"{SCHEMA_BASE}?{query}"


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
    caption = (title or "").strip()[:MAX_TITLE_CHARS]
    tags = clean_hashtags(hashtags)
    params: dict[str, str | None] = {
        "share_type": "h5",
        "client_key": client_key,
        "nonce_str": nonce,
        "timestamp": ts,
        "signature": DouyinClient.sign_share(ticket, nonce, ts),
        "video_path": video_url,
        # Straight to the publish page; the person still presses 发布 there.
        "share_to_publish": "1",
        "state": share_id or None,
        "title": caption or None,
    }
    if tags:
        params["hashtag_list"] = json.dumps(tags, ensure_ascii=False)
        if caption:
            # Inline at the end of the caption; same `start` keeps them together.
            params["title_hashtag_list"] = json.dumps(
                [{"name": t, "start": len(caption)} for t in tags], ensure_ascii=False
            )
    # Only send the newer switches when they differ from Douyin's defaults, so
    # an older app version never sees a key it does not understand.
    if private_status in (1, 2):
        params["private_status"] = str(private_status)
    if download_type == 2:
        params["download_type"] = "2"
    return serialize_share(params)


def get_share_payload(
    *,
    ticket: str,
    video_url: str,
    share_id: str | None,
    expire_at: int,
    title: str = "",
    hashtags: list[str] | None = None,
) -> dict:
    """Body for POST /api/douyin/v1/schema/get_share/ (short-link schema)."""
    caption = (title or "").strip()[:MAX_TITLE_CHARS]
    body: dict = {
        "client_ticket": ticket,
        "expire_at": int(expire_at),
        "share_to_publish": 1,
        "video_path": video_url,
    }
    if share_id:
        body["state"] = share_id
    if caption:
        body["title"] = caption
    tags = clean_hashtags(hashtags)
    if tags:
        body["hashtag_list"] = tags
    return body
