# ──────────────────────────────────────────── stdlib / 3rd‑party / local
import sys
import sys
import os
import time
from typing import List, Optional
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import uvicorn
import requests
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, ConnectionError as ESConnectionError
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import RedirectResponse
load_dotenv()

from services.search import search as hybrid_search
# ──────────────────────────────────────────── env & clients

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ES_HOST = os.getenv("ELASTICSEARCH_HOST")
ES_INDEX = os.getenv("ELASTICSEARCH_INDEX", "songs")  # Default value retained

# Spotify credentials
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

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

origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]
print(f"[CORS] Allowed origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────── pydantic models
class SearchRequest(BaseModel):
    prompt: str
    size: int = 20

class SongResult(BaseModel):
    title: str
    artist: str
    score: float
    matched_queries: List[str]
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
        hits = hybrid_search(req.prompt, req.size)
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
                spotify_url=source.get("spotify_url"),
                youtubemusic_url=source.get("youtubemusic_url"),
                popularity=source.get("popularity"),
                release_date=source.get("release_date"),
            )
        )
    return results

# ──────────────────────────────────────────── Spotify OAuth callback
@app.get("/callback", summary="Spotify OAuth callback")
def spotify_callback(request: Request):
    code = request.query_params.get("code")
    print(f"[DEBUG] Code received: {code}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    # Exchange code for access token
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        response = requests.post(token_url, data=payload, headers=headers)
        print(f"[DEBUG] Spotify response: {response.status_code}")
        print(f"[DEBUG] Response body: {response.text}")
        response.raise_for_status()
        tokens = response.json()

        access_token = tokens.get("access_token")
        if not access_token:
            return JSONResponse(status_code=500, content={"error": "Access token not found", "details": tokens})

        return RedirectResponse(url=f"http://127.0.0.1:5500/index.html?token={access_token}")

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Token exchange failed: {str(e)}")
        return JSONResponse(status_code=500, content={"error": "Token exchange failed", "details": str(e)})

# ──────────────────────────────────────────── dev runner
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5051"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
