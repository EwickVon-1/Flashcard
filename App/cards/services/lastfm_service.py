import requests
from django.conf import settings

BASE_URL = "http://ws.audioscrobbler.com/2.0/"

def search_track(query, method="track.search", limit=30):
    params = {
        "method": method,
        "api_key": settings.LASTFM_API_KEY,
        "track": query,
        "limit": limit,
        "format": "json"
    }

    response = requests.get(BASE_URL, params=params)
    if response.status_code != 200:
        return []
    data = response.json()
    tracks = data["results"]["trackmatches"]["track"]
    return [{"title": t["name"], "artist": t["artist"]} for t in tracks]

def get_track_info(artist, track):
    params = {
        "method": "track.getInfo",
        "api_key": settings.LASTFM_API_KEY,
        "artist": artist,
        "track": track,
        "format": "json",
        "autocorrect": 1
    }
    response = requests.get(BASE_URL, params=params)
    if response.status_code != 200:
        return None
    data = response.json().get("track")
    if not data:
        return None
    return {
        "title": data.get("name"),
        "artist": data.get("artist", {}).get("name"),
        "album": data.get("album", {}).get("title"),
        "album_art": data.get("album", {}).get("image", [{}])[-1].get("#text"),
        "tags": [t["name"] for t in data.get("toptags", {}).get("tag", [])[:3]],
    }

def build_flashcard_data(track_info, video_id, card_types=None):
    all_cards = {
        "song": {"question": "What is the name of this song?", "answer": track_info["title"]},
        "artist": {"question": "Who is the artist?", "answer": track_info["artist"]},
        "album": {"question": "What album is this from?", "answer": track_info["album"]},
        "genre": {"question": "What genre is this?", "answer": ", ".join(track_info["tags"])}
    }

    if card_types is None:
        card_types = ["song", "artist"]

    base_data = {
        "video_id": video_id,
        "album_art": track_info["album_art"]}
    cards = []
    for ctype in card_types:
        card = all_cards.get(ctype)
        if card and card["answer"]:
            cards.append({**base_data, **card})
    return cards
