# ───────────────────────────────────────────────────────────── imports ──
import argparse
import os
import pandas as pd
import tqdm
from elasticsearch import Elasticsearch, helpers
from openai import OpenAI
import tiktoken
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path="/Users/jiwoo/WorkSpace/MelodyMind/.env")

# Check if API key is loaded
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise SystemExit("OPENAI_API_KEY is missing. Check your .env file.")

# ───────────────────────────────────────────────────────────── CLI ──
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True, help="Directory containing hits_dataset.csv and lyrics.csv")
    ap.add_argument("--es-url", default=os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200"), help="Elasticsearch URL")
    ap.add_argument("--openai-key", default=os.getenv("OPENAI_API_KEY"), help="OpenAI API key (or set OPENAI_API_KEY in .env)")
    ap.add_argument("--batch", type=int, default=25, help="Approx records per OpenAI request (auto-split by token)")
    ap.add_argument("--max-song-tokens", type=int, default=400, help="Max tokens kept per song before embedding")
    return ap.parse_args()

# Fixed model name and embedding dimensions
EMB_MODEL = "text-embedding-3-small"
dims = 1536

# ───────────────────────────────────────────────────────────── data ──
def load_data(base: str) -> pd.DataFrame:
    """Load and merge hits and lyrics datasets."""
    hits = pd.read_csv(f"{base}/hits_dataset.csv", sep="\t", on_bad_lines="skip")
    lyrics = pd.read_csv(f"{base}/lyrics.csv", sep="\t", on_bad_lines="skip")

    hits.columns = hits.columns.str.strip()
    lyrics.columns = lyrics.columns.str.strip()

    print(f"Hits rows: {len(hits)}, Lyrics rows: {len(lyrics)}")
    merged = hits.merge(lyrics, on="song_id", how="left")
    print(f"Merged rows: {len(merged)}")
    return merged

# ─────────────────────────────────────────── Elasticsearch index ──
def create_index(es: Elasticsearch, dims: int):
    """Create the Elasticsearch index with the required mapping."""
    mapping = {
        "mappings": {
            "properties": {
                "song_id": {"type": "keyword"},
                "song_name": {"type": "text"},
                "id_artists": {"type": "keyword"},
                "name_artists": {"type": "text"},
                "popularity": {"type": "integer"},
                "explicit": {"type": "boolean"},
                "song_type": {"type": "keyword"},
                "track_number": {"type": "integer"},
                "num_artists": {"type": "integer"},
                "num_available_markets": {"type": "integer"},
                "release_date": {"type": "date"},
                "duration_ms": {"type": "integer"},
                "key": {"type": "integer"},
                "mode": {"type": "integer"},
                "time_signature": {"type": "integer"},
                "acousticness": {"type": "float"},
                "danceability": {"type": "float"},
                "energy": {"type": "float"},
                "instrumentalness": {"type": "float"},
                "liveness": {"type": "float"},
                "loudness": {"type": "float"},
                "speechiness": {"type": "float"},
                "valence": {"type": "float"},
                "tempo": {"type": "float"},
                "embedding": {  # Dense vector field
                    "type": "dense_vector",
                    "dims": dims,
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }
    es.indices.delete(index="songs", ignore=[400, 404])
    es.indices.create(index="songs", body=mapping)

# ───────────────────────────────────────────── embeddings ──
def build_embeddings(df: pd.DataFrame, client: OpenAI, model: str, approx_batch: int, max_tokens_song: int) -> pd.DataFrame:
    """Generate embeddings for the dataset."""
    enc = tiktoken.encoding_for_model(model)
    df = df.copy()

    # Clip text to max tokens
    def clip_text(text: str) -> str:
        toks = enc.encode(text)
        return enc.decode(toks[:max_tokens_song])

    df["prompt"] = (
        df["song_name"].astype(str)
        + " by "
        + df["name_artists"].astype(str)
        + "\n\n"
        + df["lyrics"].fillna("").astype(str).map(clip_text)
    )

    # Split into chunks for OpenAI API
    inputs, chunk, tot = [], [], 0
    for text in df["prompt"]:
        tlen = len(enc.encode(text))
        if chunk and (tot + tlen > 8192 or len(chunk) >= approx_batch):
            inputs.append(chunk)
            chunk, tot = [], 0
        chunk.append(text)
        tot += tlen
    if chunk:
        inputs.append(chunk)

    # Call OpenAI API
    embeds = []
    for c in tqdm.tqdm(inputs, desc="Embedding"):
        rsp = client.embeddings.create(model=model, input=c)
        embeds.extend([v.embedding for v in rsp.data])

    df["embedding"] = embeds
    return df

# ─────────────────────────────────────────── bulk loader ──
def bulk_load(es: Elasticsearch, df: pd.DataFrame):
    """Bulk load data into Elasticsearch."""
    actions = (
        {
            "_index": "songs",
            "_id": str(r.song_id),
            "_source": {
                "song_id": str(r.song_id),
                "song_name": r.song_name,
                "id_artists": r.id_artists,
                "name_artists": r.name_artists,
                "popularity": None if pd.isna(r.popularity) else int(r.popularity),
                "explicit": None if pd.isna(r.explicit) else bool(r.explicit),
                "song_type": r.song_type,
                "track_number": None if pd.isna(r.track_number) else int(r.track_number),
                "num_artists": None if pd.isna(r.num_artists) else int(r.num_artists),
                "num_available_markets": None if pd.isna(r.num_available_markets) else int(r.num_available_markets),
                "release_date": r.release_date,
                "duration_ms": None if pd.isna(r.duration_ms) else int(r.duration_ms),
                "key": None if pd.isna(r.key) else int(r.key),
                "mode": None if pd.isna(r.mode) else int(r.mode),
                "time_signature": None if pd.isna(r.time_signature) else int(r.time_signature),
                "acousticness": r.acousticness,
                "danceability": r.danceability,
                "energy": r.energy,
                "instrumentalness": r.instrumentalness,
                "liveness": r.liveness,
                "loudness": r.loudness,
                "speechiness": r.speechiness,
                "valence": r.valence,
                "tempo": r.tempo,
                "embedding": r.embedding,
                "lyrics": r.lyrics,
            }
        }
        for r in df.itertuples()
    )
    helpers.bulk(es, actions, request_timeout=120)

# ───────────────────────────────────────────────────────────── main ──
def main():
    args = parse_args()
    if not args.openai_key:
        raise SystemExit("OPENAI_API_KEY is missing. Set it in .env or pass it as a flag.")

    client = OpenAI(api_key=args.openai_key)
    es = Elasticsearch(args.es_url, request_timeout=120)

    print("· Loading CSVs")
    df = load_data(args.data_dir)

    print("· Generating embeddings")
    df = build_embeddings(df, client, EMB_MODEL, approx_batch=args.batch, max_tokens_song=args.max_song_tokens)

    print("· Creating Elasticsearch index")
    create_index(es, dims)

    print("· Bulk indexing")
    bulk_load(es, df)

    print(f"Completed. Indexed {len(df)} songs with {dims}-d vectors.")

# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
