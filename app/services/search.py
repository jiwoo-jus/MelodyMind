from functools import lru_cache
from typing import List, Optional
import os, json

from elasticsearch import Elasticsearch
from openai import OpenAI

ES = Elasticsearch(os.getenv("ELASTICSEARCH_HOST", "http://elasticsearch:9200"))
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


def search(prompt: str, size: int = 20, filters: Optional[List] = None, genre: Optional[str] = None):
    vec = embed(prompt)
    kws = keyword_expand(prompt)

    # Build the main query
    should_queries = [
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
    ]

    # Build the main bool query
    bool_query = {"should": should_queries}
    
    # NEW: Combine existing filters with genre filter
    filter_clauses = list(filters) if filters else []

    if genre:
        filter_clauses.append({
            "term": {
                "mapped_genre": genre.lower()
            }
        })

    if filter_clauses:
        bool_query["filter"] = filter_clauses

    es_query = {
        "size": size,
        "query": {
            "bool": bool_query
        }
    }
    
    res = ES.search(index="songs", body=es_query)
    return res["hits"]["hits"]
    