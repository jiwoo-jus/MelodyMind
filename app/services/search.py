from functools import lru_cache
from typing import List, Optional, Dict
import os, json

from elasticsearch import Elasticsearch, ConnectionError as ESConnectionError
from openai import OpenAI

ES_INDEX = os.getenv("ELASTICSEARCH_INDEX", "songs")

DEFAULT_ES_HOST = "http://localhost:9200"

def init_es() -> Elasticsearch:
    env_host = os.getenv("ELASTICSEARCH_HOST", DEFAULT_ES_HOST)
    hosts_to_try = [env_host]
    if env_host != "http://elasticsearch:9200":
        hosts_to_try.append("http://elasticsearch:9200")
    for h in hosts_to_try:
        try:
            es = Elasticsearch(h)
            if es.ping():
                return es
        except ESConnectionError:
            pass
    raise ESConnectionError(f"Unable to connect to Elasticsearch at {hosts_to_try}")

ES = init_es()
EMB_MODEL = "text-embedding-3-small"  # 1536-dimensional embedding

CLIENT = OpenAI()

# Generate 1536-dimensional embedding (cached)
@lru_cache(maxsize=256)
def embed(text: str) -> List[float]:
    return CLIENT.embeddings.create(model=EMB_MODEL, input=text).data[0].embedding


def keyword_expand(prompt: str) -> List[str]:
    sys = (
        "You are a music assistant. "
        "Extract up to 10 concise English keywords that best describe the prompt. "
        "Return exactly: {\"keywords\": [ ... ]}"
    )
    rsp = CLIENT.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": sys},
                  {"role": "user", "content": prompt}],
        temperature=0
    )
    try:
        data = json.loads(rsp.choices[0].message.content)
        raw = data.get("keywords", [])
    except Exception:
        raw = []
    return [str(k).strip() for k in raw if str(k).strip()]


def search(prompt: str, size: int = 20, filters: Optional[Dict[str, str]] = None, es_index: str = ES_INDEX):
    vec = embed(prompt)
    kws = keyword_expand(prompt)

    filter_clauses = []
    if filters:
        if song_name := filters.get("song_name"):
            filter_clauses.append({"match": {"song_name": song_name}})
        if artist := filters.get("artist_name"):
            filter_clauses.append({"match": {"name_artists": artist}})
        if album := filters.get("album_name"):
            filter_clauses.append({"match": {"album_name": album}})
        if song_type := filters.get("song_type"):
            filter_clauses.append({"term": {"song_type": song_type}})
        if release_date := filters.get("release_date"):
            filter_clauses.append({"match": {"release_date": release_date}})

    es_query = {
        "size": size,
        "query": {
            "bool": {
                "should": [
                    {
                        "knn": {
                            "field": "embedding",
                            "query_vector": vec,
                            "num_candidates": 100,
                            "_name": "vector_search"
                        }
                    },
                    {
                        "multi_match": {
                            "query": " ".join(kws),
                            "fields": ["song_name^3", "name_artists^2", "lyrics"],
                            "type": "most_fields",
                            "_name": "keyword_search"
                        }
                    },
                    {
                        "multi_match": {
                            "query": prompt,
                            "fields": ["song_name^3", "name_artists^2", "lyrics"],
                            "type": "most_fields",
                            "fuzziness": "AUTO",  # Allows minor typos or variations
                            "_name": "prompt_search"
                        }
                    }
                ],
                "filter": filter_clauses
            }
        }
    }
    res = ES.search(index=es_index, body=es_query)
    return res["hits"]["hits"]
