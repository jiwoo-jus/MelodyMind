from elasticsearch import Elasticsearch
import time, os, sys
from typing import Optional

def create_elasticsearch_client(es_host: str, max_retries: int = 10, retry_interval: int = 5) -> Optional[Elasticsearch]:
    """Create an Elasticsearch client with retry logic."""
    print(f"Attempting to connect to Elasticsearch at: {es_host}")
    
    for i in range(max_retries):
        try:
            es_client = Elasticsearch(es_host)
            if es_client.ping():
                print(f"Successfully connected to Elasticsearch at {es_host}")
                return es_client
            else:
                print(f"Attempt {i+1}/{max_retries}: Elasticsearch at {es_host} is not responding to ping.")
        except Exception as e:
            print(f"Attempt {i+1}/{max_retries}: Error connecting to Elasticsearch: {e}")
        
        if i < max_retries - 1:  # Don't sleep after the last attempt
            print(f"Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)
    
    print(f"Failed to connect to Elasticsearch after {max_retries} attempts.")
    return None

# Get Elasticsearch host from environment variable or use default
es_host = os.getenv("ELASTICSEARCH_HOST", "http://elasticsearch:9200")
es = create_elasticsearch_client(es_host)

if not es:
    print("Could not connect to Elasticsearch. Exiting.")
    sys.exit(1)

# Sample song data
songs = [
    {
        "title": "Midnight Drive",
        "artist": "Night Owl",
        "keywords": "desert, night, ambient, drive",
        "spotify_url": "https://open.spotify.com/track/abc123"
    },
    {
        "title": "Ocean Breeze",
        "artist": "Waveform",
        "keywords": "beach, chill, wave, relaxing",
        "spotify_url": "https://open.spotify.com/track/xyz789"
    }
]

# Create index if it doesn't exist
if not es.indices.exists(index="music_index"):
    es.indices.create(index="music_index")

# Upload songs to Elasticsearch
for i, song in enumerate(songs):
    es.index(index="music_index", id=i + 1, body=song)

print("Sample data uploaded.")