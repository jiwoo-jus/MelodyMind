# ───────────────────────────────────────────────────────────── imports ──
import argparse
import os
import pandas as pd
import tqdm
from elasticsearch import Elasticsearch, helpers
# OpenAI and tiktoken are no longer needed for embedding generation here
from dotenv import load_dotenv
import mysql.connector
import json # For parsing artists column and loading embedding

# Load environment variables
load_dotenv()

# Environment variables for DB and Elasticsearch
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "musicoset")
ES_URL = os.getenv("ELASTICSEARCH_HOST", "http://elasticsearch:9200")
ES_INDEX = os.getenv("ELASTICSEARCH_INDEX", "songs")

# Fixed model name and embedding dimensions (assuming embeddings were created with this)
# This is mainly for the Elasticsearch mapping if not dynamically fetched.
EMB_MODEL = "text-embedding-3-small" # Or your actual model
DIMS = 1536 # Or your actual embedding dimensions

# ───────────────────────────────────────────────────────────── CLI ──
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build Elasticsearch index from MySQL database.")
    ap.add_argument("--es-url", default=ES_URL, help="Elasticsearch URL")
    ap.add_argument("--es-index", default=ES_INDEX, help="Elasticsearch index name")
    # DB connection args can be added if needed, or rely on .env
    return ap.parse_args()

# ───────────────────────────────────────────────────────────── data ──
def load_data_from_db() -> pd.DataFrame:
    """Load song data from MySQL database."""
    conn = None
    try:
        print(f"Connecting to database {DB_NAME} on {DB_HOST}...")
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        if conn.is_connected():
            print("Successfully connected to the database.")

        # Adjust the JOIN based on how artists are linked.
        # This query assumes songs.artists contains a JSON-like string with artist IDs
        # and we take the first artist_id for joining with the artists table.
        # This part might need significant adjustment based on actual songs.artists structure.
        query = f"""
        SELECT
            s.song_id,
            s.song_name,
            s.artists AS s_artists,
            s.popularity,
            s.song_type,
            s.album_name,
            s.release_date,
            l.lyrics,
            e.embedding,
            ar.artist_id,
            ar.name AS name_artists,
            ar.artist_type,
            ar.main_genre,
            ar.genres,
            ar.image_url
        FROM
            songs s
        LEFT JOIN
            lyrics l ON s.song_id = l.song_id COLLATE utf8mb3_general_ci
        LEFT JOIN
            embeddings e ON s.song_id = e.song_id
        LEFT JOIN 
            artists ar ON ar.artist_id = TRIM(BOTH "'" FROM SUBSTRING_INDEX(SUBSTRING_INDEX(s.artists, "'", 2), "'", -1));
        """
        # The WHERE e.embedding IS NOT NULL ensures we only get songs with embeddings.

        print("Fetching data from database...")
        df = pd.read_sql(query, conn)
        print(f"Loaded {len(df)} songs with embeddings from database.")

        # Process artists_id and artists_name from s_artists
        # This is a simplified approach; robust parsing is needed if s_artists is complex.
        def extract_artist_info(s_artists_json_str):
            try:
                if pd.isna(s_artists_json_str) or not s_artists_json_str.strip():
                    return None, None
                # Attempt to parse as JSON, assuming format like {'id': 'name', ...}
                artists_dict = json.loads(s_artists_json_str.replace("'", "\""))
                first_artist_id = next(iter(artists_dict.keys()), None)
                first_artist_name = artists_dict.get(first_artist_id) if first_artist_id else None
                return first_artist_id, first_artist_name
            except (json.JSONDecodeError, TypeError):
                # Fallback or more sophisticated parsing might be needed
                # For now, if it's not simple JSON, we might not get these fields correctly
                # If s.artists was already joined correctly, this part might not be needed
                return None, None

        # If the JOIN for artists table was successful, artist_id and artist_name are already there.
        # If not, and you need to parse s.artists:
        # df[['id_artists_extracted', 'name_artists_extracted']] = df['s_artists'].apply(
        #     lambda x: pd.Series(extract_artist_info(x))
        # )
        # Then decide which artist fields to use. For now, assuming JOIN worked or s_artists is simple.
        # We will use 'artist_id' and 'artist_name' from the artists table join.
        # 's_artists' can be dropped if not needed further.
        # df.drop(columns=['s_artists'], inplace=True, errors='ignore')


        # Convert JSON string embedding to list
        df['embedding'] = df['embedding'].apply(lambda x: json.loads(x) if x else None)

        return df

    except mysql.connector.Error as e:
        print(f"Error connecting to MySQL or executing query: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()
            print("Database connection closed.")

# ─────────────────────────────────────────── Elasticsearch index ──
def create_index(es: Elasticsearch, index_name: str, dims: int):
    """Create the Elasticsearch index with the required mapping."""
    if es.indices.exists(index=index_name):
        print(f"Index '{index_name}' already exists. Deleting and recreating.")
        es.indices.delete(index=index_name, ignore=[400, 404])
    else:
        print(f"Creating index '{index_name}'.")

    mapping = {
        "mappings": {
            "properties": {
                "song_id": {"type": "keyword"},
                "song_name": {"type": "text", "analyzer": "standard"},
                "lyrics": {"type": "text", "analyzer": "standard"},
                "popularity": {"type": "integer"},
                "song_type": {"type": "keyword"},
                "album_name": {"type": "text", "analyzer": "standard"},
                "release_date": {"type": "date"},
                # Artist related fields from 'artists' table
                "artist_id": {"type": "keyword"}, # from artists.artist_id
                "name_artists": {"type": "text", "analyzer": "standard"}, # from artists.name
                "artist_type": {"type": "keyword"},
                "main_genre": {"type": "keyword"},
                "genres": {"type": "text"}, # Can be keyword if you don't need partial match on genres string
                "image_url": {"type": "keyword"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": dims,
                    "index": True,
                    "similarity": "cosine"
                }
                # Add other fields from your SELECT statement as needed
                # "explicit": {"type": "boolean"},
                # "track_number": {"type": "integer"},
                # "num_artists": {"type": "integer"},
                # "num_available_markets": {"type": "integer"},
                # "duration_ms": {"type": "integer"},
                # "key": {"type": "integer"},
                # "mode": {"type": "integer"},
                # "time_signature": {"type": "integer"},
                # "acousticness": {"type": "float"},
                # "danceability": {"type": "float"},
                # "energy": {"type": "float"},
                # "instrumentalness": {"type": "float"},
                # "liveness": {"type": "float"},
                # "loudness": {"type": "float"},
                # "speechiness": {"type": "float"},
                # "valence": {"type": "float"},
                # "tempo": {"type": "float"},
            }
        }
    }
    es.indices.create(index=index_name, body=mapping)
    print(f"Index '{index_name}' created with mapping.")


# build_embeddings function is removed as embeddings are pre-generated

# ─────────────────────────────────────────── bulk loader ──
def bulk_load(es: Elasticsearch, index_name: str, df: pd.DataFrame):
    """Bulk load data into Elasticsearch."""
    actions = []
    for r in df.itertuples(index=False): # index=False to avoid _0, _1 etc. as field names
        if r.embedding is None: # Skip if embedding is missing
            print(f"Skipping song_id {r.song_id} due to missing embedding.")
            continue

        source_doc = {
            "song_id": str(r.song_id),
            "song_name": r.song_name,
            "lyrics": r.lyrics,
            "popularity": None if pd.isna(r.popularity) else int(r.popularity),
            "song_type": r.song_type,
            "album_name": r.album_name,
            "release_date": r.release_date,
            "artist_id": r.artist_id, # from artists table
            "name_artists": r.name_artists, # from artists table
            "artist_type": r.artist_type,
            "main_genre": r.main_genre,
            "genres": r.genres,
            "image_url": r.image_url,
            "embedding": r.embedding,
        }
        # Clean NaN/None for text fields to avoid issues with ES
        for key in [
            "song_name",
            "lyrics",
            "song_type",
            "album_name",
            "release_date",
            "artist_id",
            "name_artists",
            "artist_type",
            "main_genre",
            "genres",
            "image_url",
        ]:
            if pd.isna(source_doc.get(key)):
                source_doc[key] = None # Or "" if you prefer empty string

        actions.append({
            "_index": index_name,
            "_id": str(r.song_id),
            "_source": source_doc
        })

    if not actions:
        print("No actions to perform for bulk load.")
        return

    print(f"Starting bulk load of {len(actions)} documents...")
    try:
        successes, errors = helpers.bulk(es, actions, request_timeout=120, raise_on_error=False)
        print(f"Bulk load completed. Successes: {successes}, Errors: {len(errors)}")
        if errors:
            print("First 5 errors:")
            for i, error_info in enumerate(errors[:5]):
                print(f"  Error {i+1}: {error_info}")
    except Exception as e:
        print(f"An exception occurred during bulk loading: {e}")


# ───────────────────────────────────────────────────────────── main ──
def main():
    args = parse_args()

    if not all([DB_USER, DB_PASSWORD, DB_NAME]):
        raise SystemExit("Database credentials (DB_USER, DB_PASSWORD, DB_NAME) are missing. Check your .env file.")

    es = Elasticsearch(args.es_url, request_timeout=120)
    if not es.ping():
        raise SystemExit(f"Failed to connect to Elasticsearch at {args.es_url}")
    print(f"Successfully connected to Elasticsearch at {args.es_url}")


    print("· Loading data from database")
    df = load_data_from_db()

    if df.empty:
        print("No data loaded from the database. Exiting.")
        return

    # Embedding generation is skipped as it's pre-loaded

    print(f"· Creating Elasticsearch index '{args.es_index}'")
    create_index(es, args.es_index, DIMS) # Pass DIMS for mapping

    print(f"· Bulk indexing to '{args.es_index}'")
    bulk_load(es, args.es_index, df)

    print(f"Completed. Indexed {len(df)} songs into '{args.es_index}'.")

# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
