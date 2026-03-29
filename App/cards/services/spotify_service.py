import spotipy

def get_spotify_client(access_token):
    return spotipy.Spotify(auth=access_token)

def search_track(sp, query, limit=10):
    results = sp.search(q=query, limit=limit, type="track")
    return results['tracks']['items']

def get_playlist_tracks(sp, playlist_id, limit=50):
    results = sp.playlist_items(playlist_id, limit=limit)
    return [item["track"] for item in results['items'] 
            if item["track"] is not None]

def build_flashcard_data(track):
    preview_url = track.get("preview_url")
    artist = track["artists"][0]["name"]
    title = track["name"]
    album_art_url = track["album"]["images"][0]["url"] if track["album"]["images"] else None
    return [
        {
            "question": "What song is this?",
            "answer": f"{title}",
            "preview_url": preview_url,
            "track_id": track["id"],
            "album_art_url": album_art_url
        },
        {
            "question": "Who is the artist?",
            "answer": f"{artist}",
            "preview_url": preview_url,
            "track_id": track["id"],
            "album_art_url": album_art_url
        }
    ]

