# ──────────────────────────────────────────── stdlib / 3rd‑party / local
import os
import time
from typing import List, Optional, Dict

import uvicorn
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, ConnectionError as ESConnectionError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.search import search as hybrid_search
# ──────────────────────────────────────────── env & clients
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ES_HOST = os.getenv("ELASTICSEARCH_HOST")
ES_INDEX = os.getenv("ELASTICSEARCH_INDEX", "songs")  # Default value retained

def init_es(host: str, retries: int = 5, wait: int = 5) -> Optional[Elasticsearch]:
    """Initialize Elasticsearch connection with retries."""
    for attempt in range(retries):
        try:
            es = Elasticsearch(host)
            if es.ping():
                print(f"[ES] Connected on attempt {attempt + 1}")
                return es
        except ESConnectionError:
            pass
        print(f"[ES] Retry {attempt + 1}/{retries} to connect to {host}…")
        time.sleep(wait)
    print("[ES] Failed to connect to Elasticsearch; health ping will be unavailable.")
    return None

es_client: Optional[Elasticsearch] = init_es(ES_HOST)

# ──────────────────────────────────────────── FastAPI app
app = FastAPI(
    title="MelodyMind API",
    description="Hybrid vector/BM25 music search powered by OpenAI + Elasticsearch.",
    version="2.0.0",
)

origins = os.getenv("CORS_ORIGINS", "").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────── pydantic models
class SearchRequest(BaseModel):
    prompt: str
    size: int = 20
    artist_name: Optional[str] = None
    album_name: Optional[str] = None
    song_type: Optional[str] = None
    release_date: Optional[str] = None

class SongResult(BaseModel):
    title: str
    artist: str
    score: float
    matched_queries: List[str]
    album_name: Optional[str] = None
    spotify_url: Optional[str] = None
    youtubemusic_url: Optional[str] = None
    popularity: Optional[int] = None
    release_date: Optional[str] = None

# ──────────────────────────────────────────── endpoints
@app.get("/", summary="Health check")
def health():
    return {
        "status": "ok",
        "elasticsearch_connected": es_client.ping() if es_client else False,
        "openai_key_loaded": bool(OPENAI_API_KEY),
    }

@app.post("/search", response_model=List[SongResult], summary="Hybrid search")
def api_search(req: SearchRequest):
    try:
        filters = {
            k: v for k, v in {
                "artist_name": req.artist_name,
                "album_name": req.album_name,
                "song_type": req.song_type,
                "release_date": req.release_date,
            }.items() if v
        }
        hits = hybrid_search(req.prompt, req.size, filters, ES_INDEX)
    except Exception as e:
        print(f"Unhandled exception in hybrid_search: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail=f"Search backend error: {str(e)}")

    results: List[SongResult] = []
    for h in hits:
        source = h.get("_source", {})

        results.append(
            SongResult(
                title=source.get("song_name", "Unknown Title"),
                artist=source.get("name_artists", "Unknown Artist"),
                score=h.get("_score", 0.0),
                matched_queries=h.get("matched_queries", []),
                album_name=source.get("album_name"),
                spotify_url=source.get("spotify_url"),
                youtubemusic_url=source.get("youtubemusic_url"),
                popularity=source.get("popularity"),
                release_date=source.get("release_date"),
            )
        )
    return results

# ──────────────────────────────────────────── dev runner
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5051"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
