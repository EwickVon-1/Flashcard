from google.oauth2.credentials import Credentials
import googleapiclient.discovery

def get_youtube_client(access_token):
    credentials = Credentials(token=access_token)
    return googleapiclient.discovery.build(
        "youtube", "v3", credentials=credentials
    )

def build_search_query(track_info):
    return f"{track_info['artist']} {track_info['title']} official"

def search_videos(yt, query, limit=5):
    results = yt.search().list(q=query, 
                               part="snippet",
                               type="video",
                               videoCategoryId="10",  # Music category
                               maxResults=limit).execute()
    return [{
        "video_id": item["id"]["videoId"],
        "title": item["snippet"]["title"],
        "channel": item["snippet"]["channelTitle"],
        "thumbnail": item["snippet"]["thumbnails"]["high"]["url"] if "high" in item["snippet"]["thumbnails"] else None
    } for item in results.get("items", [])]

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
