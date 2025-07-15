# ──────────────────────────────────────────── stdlib / 3rd‑party / local
import sys
import sys
import os
import time
from typing import List, Optional
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import uvicorn
import requests
import mysql.connector
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, ConnectionError as ESConnectionError
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import RedirectResponse
load_dotenv()

from services.search import search as hybrid_search
# ──────────────────────────────────────────── env & clients

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ES_HOST = os.getenv("ELASTICSEARCH_HOST")
ES_INDEX = os.getenv("ELASTICSEARCH_INDEX", "songs")  # Default value retained

# MySQL database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "musicoset")

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

def get_db_connection():
    """Get MySQL database connection."""
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
    except mysql.connector.Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

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
    energy_min: Optional[float] = None
    energy_max: Optional[float] = None
    artist: Optional[str] = None
    popularity_min: Optional[int] = None
    popularity_max: Optional[int] = None

class SongResult(BaseModel):
    title: str
    artist: str
    score: float
    matched_queries: List[str]
    spotify_url: Optional[str] = None
    youtube_music_url: Optional[str] = None
    popularity: Optional[int] = None
    release_date: Optional[str] = None
    energy: Optional[float] = None
    lyrics: Optional[str] = None
    reason: Optional[str] = None

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
        # Build filter conditions for Elasticsearch
        filters = []
        
        # Energy filter
        if req.energy_min is not None or req.energy_max is not None:
            energy_range = {}
            if req.energy_min is not None:
                energy_range["gte"] = req.energy_min
            if req.energy_max is not None:
                energy_range["lte"] = req.energy_max
            filters.append({"range": {"energy": energy_range}})
        
        # Artist filter
        if req.artist:
            filters.append({"match": {"name_artists": req.artist}})
        
        # Popularity filter
        if req.popularity_min is not None or req.popularity_max is not None:
            popularity_range = {}
            if req.popularity_min is not None:
                popularity_range["gte"] = req.popularity_min
            if req.popularity_max is not None:
                popularity_range["lte"] = req.popularity_max
            filters.append({"range": {"popularity": popularity_range}})
        
        hits = hybrid_search(req.prompt, req.size, filters)
    except Exception as e:
        print(f"Unhandled exception in hybrid_search: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail=f"Search backend error: {str(e)}")

    # Get additional data from MySQL
    db_conn = get_db_connection()
    song_data = {}
    
    if db_conn:
        try:
            cursor = db_conn.cursor(dictionary=True)
            song_ids = [h.get("_source", {}).get("song_id") for h in hits if h.get("_source", {}).get("song_id")]
            
            if song_ids:
                # Get release dates from tracks table
                placeholders = ",".join(["%s"] * len(song_ids))
                release_query = f"""
                SELECT song_id, release_date 
                FROM tracks 
                WHERE song_id IN ({placeholders})
                """
                cursor.execute(release_query, song_ids)
                release_data = {row["song_id"]: row["release_date"] for row in cursor.fetchall()}
                
                # Get YouTube Music URLs from melodymind_song_links table
                youtube_query = f"""
                SELECT song_id, youtube_music_url 
                FROM melodymind_song_links 
                WHERE song_id IN ({placeholders})
                """
                cursor.execute(youtube_query, song_ids)
                youtube_data = {row["song_id"]: row["youtube_music_url"] for row in cursor.fetchall()}
                
                # Get energy from acoustic_features table
                energy_query = f"""
                SELECT song_id, energy 
                FROM acoustic_features 
                WHERE song_id IN ({placeholders})
                """
                cursor.execute(energy_query, song_ids)
                energy_data = {row["song_id"]: float(row["energy"]) if row["energy"] else None for row in cursor.fetchall()}
                
                # Combine all data
                for song_id in song_ids:
                    song_data[song_id] = {
                        "release_date": release_data.get(song_id),
                        "youtube_music_url": youtube_data.get(song_id),
                        "energy": energy_data.get(song_id)
                    }
            
            cursor.close()
        except mysql.connector.Error as e:
            print(f"Error querying MySQL: {e}")
        finally:
            db_conn.close()

    results: List[SongResult] = []
    for h in hits:
        source = h.get("_source", {})
        song_id = source.get("song_id")
        additional_data = song_data.get(song_id, {})

        results.append(
            SongResult(
                title=source.get("song_name", "Unknown Title"),
                artist=source.get("name_artists", "Unknown Artist"),
                score=h.get("_score", 0.0),
                matched_queries=h.get("matched_queries", []),
                spotify_url=source.get("spotify_url"),
                youtube_music_url=additional_data.get("youtube_music_url") or source.get("youtube_music_url"),
                popularity=source.get("popularity"),
                release_date=additional_data.get("release_date") or source.get("release_date"),
                energy=additional_data.get("energy") or source.get("energy"),
                lyrics=source.get("lyrics"),
                reason=source.get("reason"),
            )
        )
    return results

@app.get("/search", response_model=List[SongResult], summary="Hybrid search via GET")
def api_search_get(
    prompt: str = Query(..., description="Search prompt"),
    size: int = Query(20, description="Number of results to return"),
    energy_min: Optional[float] = Query(None, description="Minimum energy level"),
    energy_max: Optional[float] = Query(None, description="Maximum energy level"),
    artist: Optional[str] = Query(None, description="Artist name filter"),
    popularity_min: Optional[int] = Query(None, description="Minimum popularity"),
    popularity_max: Optional[int] = Query(None, description="Maximum popularity")
):
    """GET version of the search endpoint with query parameters."""
    req = SearchRequest(
        prompt=prompt,
        size=size,
        energy_min=energy_min,
        energy_max=energy_max,
        artist=artist,
        popularity_min=popularity_min,
        popularity_max=popularity_max
    )
    return api_search(req)

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
