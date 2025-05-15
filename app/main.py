# app/main.py
import os, json, time
import openai
from typing import List, Optional
from elasticsearch import Elasticsearch, ConnectionError as ESConnectionError, NotFoundError as ESNotFoundError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file at the beginning
load_dotenv()

# --- Configuration ---
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini') # Default to gpt-4o-mini if not specified

# Elasticsearch Configuration
ES_HOST = os.getenv("ELASTICSEARCH_HOST", "http://elasticsearch:9200")
ES_INDEX_NAME = "music_index"

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Music Recommender API",
    description="API for recommending music based on user prompts using OpenAI and Elasticsearch.",
    version="1.0.0"
)

# --- CORS Middleware Configuration ---
# Define allowed origins for CORS. Adjust as necessary for frontend deployment.
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:5051",
    # Add deployed frontend URL here when applicable
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Clients ---
# Initialize OpenAI client
openai_client: Optional[openai.OpenAI] = None
if OPENAI_API_KEY:
    try:
        openai_client = openai.OpenAI(
            api_key=OPENAI_API_KEY
        )
        print("OpenAI client initialized successfully. model:", OPENAI_MODEL)
    except Exception as e:
        print(f"OpenAI client initialization error: {e}. Check API key in .env file.")
        openai_client = None
else:
    print("Warning: OPENAI_API_KEY environment variable is not set. OpenAI client will not be initialized.")

# Initialize Elasticsearch client
es_client: Optional[Elasticsearch] = None

def initialize_elasticsearch_client(host: str, max_retries: int = 5, retry_interval: int = 5) -> Optional[Elasticsearch]:
    """Initializes and returns an Elasticsearch client with retry logic."""
    print(f"Attempting to connect to Elasticsearch at: {host}")
    for attempt in range(max_retries):
        try:
            client = Elasticsearch(host)
            if client.ping():
                print(f"Successfully connected to Elasticsearch at {host} on attempt {attempt + 1}.")
                return client
            else:
                print(f"Attempt {attempt + 1}/{max_retries}: Elasticsearch at {host} is not responding to ping.")
        except ESConnectionError as e:
            print(f"Attempt {attempt + 1}/{max_retries}: Elasticsearch connection error: {e}")
        except Exception as e: # Catch other potential exceptions during client instantiation
            print(f"Attempt {attempt + 1}/{max_retries}: Error initializing Elasticsearch client: {e}")

        if attempt < max_retries - 1:
            print(f"Retrying Elasticsearch connection in {retry_interval} seconds...")
            time.sleep(retry_interval)
    
    print(f"Failed to connect to Elasticsearch after {max_retries} attempts.")
    return None

# Call initialization at startup
es_client = initialize_elasticsearch_client(ES_HOST)


# --- Pydantic Models for Request and Response ---
class PromptInput(BaseModel):
    prompt: str

class SongResult(BaseModel):
    title: str
    artist: str
    match_score: float
    reason: str
    spotify_url: Optional[str] = None

# --- Helper Functions ---
def extract_keywords_with_openai(prompt_text: str) -> List[str]:
    """
    Extracts music-related keywords from a user prompt using OpenAI.
    """
    if not openai_client:
        print("OpenAI client is not available for keyword extraction.")
        raise HTTPException(status_code=503, detail="OpenAI service is not configured or unavailable.")

    system_message = (
        "You are a music assistant. Extract 3 to 5 music-related keywords from the user query. "
        "You MUST respond with a valid JSON object. This JSON object must have a single key named 'keywords', "
        "and the value of this key must be an array of strings. "
        "For example: {\"keywords\": [\"night\", \"desert\", \"driving\"]}. "
        "Ensure your entire output is ONLY this valid JSON object itself, with no extra text before or after."
    )
    
    try:
        print(f"Sending prompt to OpenAI for keyword extraction: '{prompt_text}'")
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt_text}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        content = response.choices[0].message.content
        print(f"OpenAI raw response for keywords: {content}")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            error_detail = f"OpenAI response was not valid JSON. Raw content: '{content}'. Error: {str(e)}"
            print(error_detail)
            raise HTTPException(status_code=500, detail=error_detail)

        keywords_from_llm = data.get("keywords")

        # Handle cases where LLM might not return the exact expected structure
        if keywords_from_llm is None:
            if isinstance(data, list) and all(isinstance(kw, str) for kw in data):
                print("Warning: LLM returned a JSON array directly instead of {'keywords': [...]}. Using the array.")
                keywords_from_llm = data
            else:
                error_detail = f"JSON from LLM does not contain 'keywords' key or a direct list. Parsed data: '{data}'"
                print(error_detail)
                raise HTTPException(status_code=500, detail=error_detail)
        
        if not isinstance(keywords_from_llm, list):
            error_detail = f"'keywords' field from LLM is not a list. Found: {type(keywords_from_llm)}. Data: '{data}'"
            print(error_detail)
            raise HTTPException(status_code=500, detail=error_detail)

        # Clean and validate keywords
        cleaned_keywords = [
            str(kw).strip() for kw in keywords_from_llm if isinstance(kw, (str, int, float)) and str(kw).strip()
        ]
        
        if not cleaned_keywords and keywords_from_llm:
            print(f"Warning: All items in 'keywords' list were invalid or empty after cleaning. Original LLM list: {keywords_from_llm}")
        
        print(f"Cleaned keywords from OpenAI: {cleaned_keywords}")
        return cleaned_keywords

    except HTTPException:
        raise
    except openai.APIConnectionError as e:
        print(f"OpenAI API connection error: {e}")
        raise HTTPException(status_code=504, detail=f"Failed to connect to OpenAI: {str(e)}")
    except openai.APIStatusError as e:
        print(f"OpenAI API status error: {e.status_code} - {e.response}")
        raise HTTPException(status_code=e.status_code, detail=f"OpenAI API error: {e.message if hasattr(e, 'message') else str(e)}")
    except Exception as e:
        error_detail = f"Unexpected error during keyword extraction with OpenAI: {str(e)}. Prompt: '{prompt_text}'"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)

# --- API Endpoints ---
@app.get("/", summary="Health Check")
def health_check_root():
    """
    Provides a basic health check for the API, including connectivity status
    for Elasticsearch and initialization status for OpenAI.
    """
    es_connected = False
    if es_client:
        try:
            es_connected = es_client.ping()
        except ESConnectionError:
            es_connected = False
        except Exception as e:
            print(f"Error pinging Elasticsearch during health check: {e}")
            es_connected = False
            
    return {
        "message": "Music Recommender API is operational.",
        "elasticsearch_host_configured": ES_HOST,
        "elasticsearch_connection_status": "connected" if es_connected else "disconnected",
        "openai_client_initialized": openai_client is not None
    }

@app.post("/api/search", response_model=List[SongResult], summary="Search Music Recommendations")
def search_music(input_data: PromptInput):
    """
    Accepts a user prompt, extracts keywords using OpenAI,
    searches Elasticsearch for matching songs, and returns a list of recommendations.
    """
    if not es_client:
        print(f"Search request failed: Elasticsearch client unavailable (target host: {ES_HOST}).")
        raise HTTPException(status_code=503, detail=f"Elasticsearch service is not available. Check connection to {ES_HOST}.")
    if not openai_client:
        print("Search request failed: OpenAI client unavailable.")
        raise HTTPException(status_code=503, detail="OpenAI service is not configured or unavailable.")

    try:
        keywords = extract_keywords_with_openai(input_data.prompt)  # Updated function name
        if not keywords:
            print(f"No valid keywords extracted for prompt: '{input_data.prompt}'. Returning empty list.")
            return []

        # Construct Elasticsearch query
        es_query_body = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"keywords": keyword}} for keyword in keywords
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": 20
        }
        print(f"Constructed Elasticsearch query: {json.dumps(es_query_body, indent=2)}")
        
        try:
            search_results = es_client.search(index=ES_INDEX_NAME, body=es_query_body)
        except ESNotFoundError:
            print(f"Elasticsearch index '{ES_INDEX_NAME}' not found.")
            raise HTTPException(status_code=404, detail=f"Search index '{ES_INDEX_NAME}' not found. Please ensure data is indexed.")
        except ESConnectionError as e:
            print(f"Elasticsearch search connection error: {e}")
            raise HTTPException(status_code=503, detail=f"Could not connect to Elasticsearch for searching at {ES_HOST}.")
        except Exception as e:
            print(f"Elasticsearch general search error: {e}")
            raise HTTPException(status_code=500, detail=f"Error during Elasticsearch search: {str(e)}")

        # Process search results
        output_songs: List[SongResult] = []
        for hit in search_results.get("hits", {}).get("hits", []):
            source_data = hit.get("_source", {})
            output_songs.append(SongResult(
                title=source_data.get("title", "Unknown Title"),
                artist=source_data.get("artist", "Unknown Artist"),
                match_score=hit.get("_score", 0.0),
                reason=f"Matched on keywords: {', '.join(keywords)}",
                spotify_url=source_data.get("spotify_url")
            ))
        
        if not output_songs:
            print(f"No music found in Elasticsearch for keywords: {keywords}")
        
        return output_songs

    except HTTPException:
        raise
    except Exception as e:
        print(f"An unexpected error occurred in search_music endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# --- Uvicorn Runner (for local development) ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "5051"))
    reload_flag = os.getenv("UVICORN_RELOAD", "False").lower() in ("true", "1", "t")
    
    print(f"Starting Uvicorn server on host 0.0.0.0, port {port}, reload: {reload_flag}")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=reload_flag
    )