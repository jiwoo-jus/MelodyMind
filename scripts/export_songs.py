from elasticsearch import Elasticsearch
import json

es = Elasticsearch("http://localhost:9200")

index_name = "songs"
page_size = 1000  # Number of documents per request
all_hits = []

# Initial search
response = es.search(
    index=index_name,
    body={
        "query": {"match_all": {}},
        "sort": [{"song_id": "asc"}],
        "size": page_size
    }
)

hits = response["hits"]["hits"]
all_hits.extend(hits)

# Continue fetching using search_after
while len(hits) > 0:
    last_sort = hits[-1]["sort"]
    response = es.search(
        index=index_name,
        body={
            "query": {"match_all": {}},
            "sort": [{"song_id": "asc"}],
            "size": page_size,
            "search_after": last_sort
        }
    )
    hits = response["hits"]["hits"]
    all_hits.extend(hits)

# Save all documents to a JSON file
with open("songs_data.json", "w") as f:
    json.dump(all_hits, f, indent=2)

print(f"Exported {len(all_hits)} documents to songs_data.json")