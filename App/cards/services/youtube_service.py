from google.oauth2.credentials import Credentials
import googleapiclient.discovery

from django.core.cache import cache

def get_youtube_client(access_token):
    credentials = Credentials(token=access_token)
    return googleapiclient.discovery.build(
        "youtube", "v3", credentials=credentials
    )

def build_search_query(track_info):
    return f"{track_info['artist']} {track_info['title']} audio"

def search_videos(yt, query, limit=2):
    results = yt.search().list(q=query, 
                               part="snippet",
                               type="video",
                               videoEmbeddable="true",
                               videoCategoryId="10",  # Music category
                               maxResults=limit).execute()
    return [{
        "video_id": item["id"]["videoId"],
        "title": item["snippet"]["title"],
        "channel": item["snippet"]["channelTitle"],
        "thumbnail": item["snippet"]["thumbnails"]["high"]["url"] if "high" in item["snippet"]["thumbnails"] else None
    } for item in results.get("items", [])]

def filter_embeddable(yt, videos):
    ids = ",".join(v["video_id"] for v in videos)
    result = yt.videos().list(part="status", id=ids).execute()
    embeddable_ids = {
        item["id"] for item in result.get("items", [])
        if item["status"].get("embeddable", False)
    }
    return [v for v in videos if v["video_id"] in embeddable_ids]

def get_playlist_videos(yt, playlist_id, limit=50):
    results = yt.playlistItems().list(playlistId=playlist_id, 
                                      part="snippet", 
                                      maxResults=limit).execute()
    return [{
        "video_id": item["snippet"]["resourceId"]["videoId"],
        "title": item["snippet"]["title"],
        "channel": item["snippet"]["channelTitle"],
        "thumbnail": item["snippet"]["thumbnails"]["high"]["url"] if "high" in item["snippet"]["thumbnails"] else None
    } for item in results.get("items", [])]
