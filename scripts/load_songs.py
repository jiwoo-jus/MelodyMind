from elasticsearch import Elasticsearch, helpers
import json

# Connect to Elasticsearch
es = Elasticsearch("http://localhost:9200")

# Load the JSON file
with open("songs_data.json", "r") as f:
    songs = json.load(f)

# Prepare bulk actions
actions = [
    {
        "_index": "songs",
        "_id": song["_id"],
        "_source": song["_source"]
    }
    for song in songs
]

# Bulk load data into Elasticsearch
helpers.bulk(es, actions)

print("Data successfully loaded into Elasticsearch.")