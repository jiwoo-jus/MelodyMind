from elasticsearch import Elasticsearch, helpers
import json
import pandas as pd
import math

# Connect to Elasticsearch
es = Elasticsearch("http://localhost:9200")

# Load the JSON file
with open("songs_data.json", "r") as f:
    songs_raw = json.load(f)

# NaN -> None
def clean_nan_values(obj):
    if isinstance(obj, dict):
        return {k: clean_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan_values(elem) for elem in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None 
    return obj

songs = []
for song_item_raw in songs_raw:
    if "_source" in song_item_raw and isinstance(song_item_raw["_source"], dict):
        song_item_raw["_source"] = clean_nan_values(song_item_raw["_source"])
    songs.append(song_item_raw)

print(f"Loaded and cleaned {len(songs)} songs from songs_data.json")


# Load lyrics
lyrics_df = pd.read_csv("/Users/jiwoo/WorkSpace/MelodyMind/data/musicoset/lyrics.csv", sep="\t")
lyrics_df.columns = lyrics_df.columns.str.strip()
lyrics_dict = dict(zip(lyrics_df.song_id, lyrics_df.lyrics))

# Add lyrics to songs
match_count = 0
for song in songs:
    song_id = song["_id"]
    lyrics_text = lyrics_dict.get(song_id)
    if pd.notna(lyrics_text):
        song["_source"]["lyrics"] = lyrics_text
        match_count += 1
    else:
        song["_source"]["lyrics"] = None


print(f"Added lyrics to {match_count} songs")

if es.indices.exists(index="songs"):
    es.indices.delete(index="songs")
    print("Deleted existing 'songs' index")

mapping = {
    "mappings": {
        "properties": {
            "song_id": {"type": "keyword"},
            "song_name": {"type": "text"},
            "id_artists": {"type": "keyword"},
            "name_artists": {"type": "text"},
            "popularity": {"type": "integer"},
            "explicit": {"type": "boolean"},
            "song_type": {"type": "keyword"},
            "track_number": {"type": "integer"},
            "num_artists": {"type": "integer"},
            "num_available_markets": {"type": "integer"},
            "release_date": {"type": "date"},
            "duration_ms": {"type": "integer"},
            "key": {"type": "integer"},
            "mode": {"type": "integer"},
            "time_signature": {"type": "integer"},
            "acousticness": {"type": "float"},
            "danceability": {"type": "float"},
            "energy": {"type": "float"},
            "instrumentalness": {"type": "float"},
            "liveness": {"type": "float"},
            "loudness": {"type": "float"},
            "speechiness": {"type": "float"},
            "valence": {"type": "float"},
            "tempo": {"type": "float"},
            "embedding": {
                "type": "dense_vector",
                "dims": 1536,
                "index": True,
                "similarity": "cosine"
            },
            "lyrics": {"type": "text"}
        }
    }
}

es.indices.create(index="songs", body=mapping)
print("Created new 'songs' index with complete mapping")

# Prepare bulk actions
actions = [
    {
        "_index": "songs",
        "_id": song["_id"],
        "_source": song["_source"]
    }
    for song in songs
]

print("Starting bulk indexing...")
success_count = 0
failed_count = 0
failed_items_details = []

for ok, action_info in helpers.streaming_bulk(
    client=es, actions=actions, raise_on_error=False, request_timeout=120
):
    if not ok:
        failed_count += 1
        error_details = action_info.get('index', action_info.get('create', {}))
        doc_id = error_details.get('_id', 'Unknown ID')
        status = error_details.get('status', 'Unknown Status')
        error_info = error_details.get('error', {})
        error_type = error_info.get('type', 'Unknown Error Type')
        error_reason = error_info.get('reason', 'No reason provided')
        
        caused_by = error_info.get('caused_by', {})
        caused_by_reason = caused_by.get('reason', '')
        
        detailed_error_msg = f"Doc ID: {doc_id}, Status: {status}, Type: {error_type}, Reason: {error_reason}"
        if caused_by_reason:
            detailed_error_msg += f" | Caused by: {caused_by_reason}"
            
        failed_items_details.append(detailed_error_msg)
    else:
        success_count += 1

    if (success_count + failed_count) % 1000 == 0:
        print(f"Processed {success_count + failed_count} documents (Succeeded: {success_count}, Failed: {failed_count})...")

print(f"Bulk indexing completed. Succeeded: {success_count}, Failed: {failed_count}")

if failed_items_details:
    print("\nDetails of failed documents:")
    for i, detail in enumerate(failed_items_details):
        print(f"{i+1}. {detail}")
else:
    print("All documents indexed successfully.")