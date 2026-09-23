"""Companion YouTube videos per topic.

With a YouTube Data API key we return real, embeddable videos. Without one we return
targeted search links, so the feature still works on a zero-config deploy.
"""

from __future__ import annotations

import html
import logging
from urllib.parse import quote_plus

import httpx

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def search_links(query: str) -> dict:
    variants = [
        ("Explained simply", f"{query}"),
        ("Full lecture", f"{query} lecture"),
        ("Exam revision", f"{query} revision"),
    ]
    return {
        "mode": "search",
        "items": [],
        "links": [
            {"label": label, "query": q, "url": f"https://www.youtube.com/results?search_query={quote_plus(q)}"}
            for label, q in variants
        ],
    }


async def find_videos(query: str, api_key: str, max_results: int = 4, client: httpx.AsyncClient | None = None) -> dict:
    query = (query or "").strip()[:150]
    if not query:
        return {"mode": "search", "items": [], "links": []}
    if not api_key:
        return search_links(query)

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "videoEmbeddable": "true",
        "safeSearch": "strict",
        "relevanceLanguage": "en",
        "key": api_key,
    }
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=15)
    try:
        resp = await client.get(SEARCH_URL, params=params)
        resp.raise_for_status()
        items = []
        for it in resp.json().get("items", []):
            vid = it.get("id", {}).get("videoId")
            sn = it.get("snippet", {})
            if not vid:
                continue
            thumbs = sn.get("thumbnails", {})
            thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
            items.append(
                {
                    "video_id": vid,
                    "title": html.unescape(sn.get("title", "")),
                    "channel": html.unescape(sn.get("channelTitle", "")),
                    "thumbnail": thumb,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                }
            )
        result = search_links(query)
        result.update({"mode": "api", "items": items})
        return result
    except Exception as exc:  # noqa: BLE001 — never let this optional feature fail a topic
        log.warning("YouTube search failed for %r: %s", query, exc)
        return search_links(query)
    finally:
        if own_client:
            await client.aclose()
