from re import compile
from cards.services.lastfm_service import search_track
from cards.services.youtube_service import (
    build_search_query,
    get_youtube_client,
    search_videos,
)
from cards.utils.google_oauth import get_valid_token

from django.core.cache import cache

YOUTUBE_ID_PATTERN = compile("^[A-Za-z0-9_-]{11}$")


def is_valid_video(video_id) -> bool:
    if not YOUTUBE_ID_PATTERN.fullmatch(video_id):
        return False
    return True


def is_video_embeddable(request, video_id):
    # Returns True if Youtube confirms that video exists and is embeddable
    token = get_valid_token(request.user)
    if not token:
        return None

    yt = get_youtube_client(token)
    response = (
        yt.videos()
        .list(
            part="status",
            id=video_id,
        )
        .execute()
    )

    items = response.get("items", [])
    if not items:
        return False

    status = items[0].get("status", {})
    return status.get("embeddable") is True


def search_videos_cached(yt, query, limit=2):
    cache_key = f"yt_{query.replace(' ', '_')}"
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    result = search_videos(yt, query, limit=limit)
    cache.set(cache_key, result, timeout=60 * 60)  # Cache for 1 hour
    return result


def search_tracks_with_videos(request, query, track_limit=3, video_limit=1):
    token = get_valid_token(request.user)
    if not token:
        return None
    tracks = search_track(query, limit=track_limit)
    yt = get_youtube_client(token)
    results = []
    for track in tracks:
        query = build_search_query(track)
        videos = search_videos_cached(yt, query, limit=video_limit)
        results.append({**track, "videos": videos})
    return results
