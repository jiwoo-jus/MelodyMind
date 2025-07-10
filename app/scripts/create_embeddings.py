import argparse
import os
import pandas as pd
import json
import tqdm
from openai import OpenAI
import tiktoken
from dotenv import load_dotenv
import mysql.connector
import logging # New import
from datetime import datetime # New import

# --- Global Log Counter for custom numbering ---
# This will be managed by the custom formatter

# --- Setup Logger ---
def setup_logger():
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        print(f"Created directory: {logs_dir}") # Initial print, logger not fully set up yet

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(logs_dir, f"embedding_log_{timestamp}.log")

    logger_instance = logging.getLogger("embedding_script")
    logger_instance.setLevel(logging.INFO)

    # Prevent multiple handlers if script/logger setup is called multiple times
    if logger_instance.hasHandlers():
        logger_instance.handlers.clear()

    # Custom Formatter with sequential numbering
    class SequentialFormatter(logging.Formatter):
        def __init__(self, fmt=None, datefmt=None, style='%', validate=True):
            super().__init__(fmt, datefmt, style, validate)
            self.entry_number = 0

        def format(self, record):
            self.entry_number += 1
            record.entry_number = self.entry_number
            return super().format(record)

    formatter = SequentialFormatter(
        "[%(entry_number)d] [%(asctime)s] [%(levelname)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File Handler
    fh = logging.FileHandler(log_filename, encoding='utf-8')
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger_instance.addHandler(fh)

    # Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger_instance.addHandler(ch)

    return logger_instance

logger = setup_logger()

# Load environment variables
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
EMB_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "musicoset")

# Log environment variables (mask API_KEY)
masked_api_key = f"{API_KEY[:7]}...{API_KEY[-4:]}" if API_KEY and len(API_KEY) > 11 else "Not Set or Too Short"
logger.info(f'Environment variables loaded.\nAPI_KEY: {masked_api_key}\nEMB_MODEL: {EMB_MODEL}\nDB_HOST: {DB_HOST}\nDB_USER: {DB_USER}\nDB_NAME: {DB_NAME}')

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Create embeddings for songs and save to MySQL database.")
    ap.add_argument("--openai-key", default=API_KEY, help="OpenAI API key")
    ap.add_argument("--batch-size", type=int, default=25, help="Approximate records per OpenAI request")
    ap.add_argument("--max-song-tokens", type=int, default=400, help="Maximum tokens kept per song before embedding")
    return ap.parse_args()

def load_and_prepare_data() -> pd.DataFrame:
    """Load song data from MySQL database, and prepare text for embedding."""
    conn = None
    try:
        logger.info(f"Connecting to database {DB_NAME} on {DB_HOST}...")
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        if conn.is_connected():
            logger.info("Successfully connected to the database.")

        query = """
        SELECT
            s.song_id AS song_id,
            s.billboard AS billboard_info, 
            l.lyrics AS lyrics
        FROM
            songs s
        LEFT JOIN
            lyrics l ON s.song_id = l.song_id COLLATE utf8mb3_general_ci
        """
        logger.info("Fetching data from database...")
        db_df = pd.read_sql(query, conn)
        logger.info(f"Loaded data from database. Total songs: {len(db_df)}")

        db_df['song_id'] = db_df['song_id'].astype(str)
        db_df["lyrics"] = db_df["lyrics"].fillna("")
        db_df["billboard_info"] = db_df["billboard_info"].fillna("").astype(str) # Ensure billboard_info is string and handle NULL
        
        # Construct prompt using billboard_info and lyrics
        # Add a separator if billboard_info is not empty
        db_df["prompt"] = db_df.apply(
            lambda row: f"{row['billboard_info']}\n\n{row['lyrics']}" if row['billboard_info'] else row['lyrics'],
            axis=1
        )
        return db_df

    except mysql.connector.Error as e:
        logger.error(f"Error connecting to MySQL or executing query: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()
            logger.info("Database connection closed.")

def create_embeddings_table():
    """Create the embeddings table in the database if it doesn't exist."""
    conn = None
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()
        table_creation_query = """
        CREATE TABLE IF NOT EXISTS embeddings (
            song_id VARCHAR(22) NOT NULL PRIMARY KEY,
            embedding JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
        """
        cursor.execute(table_creation_query)
        conn.commit()
        logger.info("Ensured 'embeddings' table exists.")
    except mysql.connector.Error as e:
        logger.error(f"Error creating 'embeddings' table: {e}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def generate_embeddings(df: pd.DataFrame, client: OpenAI, model: str, batch_size: int, max_tokens_song: int) -> list:
    """Generate embeddings for the dataset."""
    enc = tiktoken.encoding_for_model(model)
    embeddings_data = []

    def clip_text(text: str) -> str:
        tokens = enc.encode(text)
        return enc.decode(tokens[:max_tokens_song])

    prepared_prompts_for_batching = []
    for index, row in df.iterrows():
        full_prompt = row["prompt"] # This now contains billboard_info + lyrics
        clipped_prompt = clip_text(full_prompt)
        prepared_prompts_for_batching.append({
            "song_id": row["song_id"],
            "clipped_prompt": clipped_prompt,
            "original_billboard_info": row["billboard_info"], # Keep for logging
            "original_lyrics": row["lyrics"] # Keep for logging
        })

    for i in tqdm.tqdm(range(0, len(prepared_prompts_for_batching), batch_size), desc="Generating Embeddings"):
        batch_data_with_ids = prepared_prompts_for_batching[i:i + batch_size]
        batch_prompts_text_to_send = [item["clipped_prompt"] for item in batch_data_with_ids]
        
        try:
            if batch_prompts_text_to_send:
                for item_idx, prompt_text_content in enumerate(batch_prompts_text_to_send):
                    current_song_id = batch_data_with_ids[item_idx]["song_id"]
                    # Log the full clipped prompt being sent (or its start)
                    truncated_prompt_for_log = prompt_text_content[:60] + "..." if len(prompt_text_content) > 60 else prompt_text_content
                    logger.info(f"Sending to API for song_id: {current_song_id} | Full Prompt (start): {truncated_prompt_for_log}")

            response = client.embeddings.create(model=model, input=batch_prompts_text_to_send)
            
            for idx, embedding_data_point in enumerate(response.data):
                song_id_for_log = batch_data_with_ids[idx]["song_id"]
                original_billboard_info_for_log = batch_data_with_ids[idx]["original_billboard_info"]
                original_lyrics_for_log = batch_data_with_ids[idx]["original_lyrics"]

                truncated_billboard_display = original_billboard_info_for_log[:40] + "..." if len(original_billboard_info_for_log) > 40 else original_billboard_info_for_log
                truncated_lyrics_display = original_lyrics_for_log[:30] + "..." if len(original_lyrics_for_log) > 30 else original_lyrics_for_log
                
                generated_embedding_vector = embedding_data_point.embedding
                truncated_embedding_display = str(generated_embedding_vector[:3])[:10] + "..." if generated_embedding_vector and len(str(generated_embedding_vector[:3])) > 10 else str(generated_embedding_vector[:3])

                logger.info(f"Received embedding for song_id: {song_id_for_log} | "
                              f"Billboard: {truncated_billboard_display} | "
                              f"Lyrics: {truncated_lyrics_display} | "
                              f"Embedding: {truncated_embedding_display}")
                
                embeddings_data.append({
                    "song_id": song_id_for_log,
                    "embedding": generated_embedding_vector
                })
        except Exception as e:
            logger.error(f"Error processing batch starting with song_id {batch_data_with_ids[0]['song_id'] if batch_data_with_ids else 'N/A'}: {e}")
            for idx_in_batch, item_in_batch in enumerate(batch_data_with_ids):
                original_item_index = i + idx_in_batch
                song_id_for_error_log = prepared_prompts_for_batching[original_item_index]["song_id"]
                logger.warning(f"Marking embedding as None for song_id: {song_id_for_error_log} due to batch error.")
                embeddings_data.append({
                    "song_id": song_id_for_error_log,
                    "embedding": None
                })
    return embeddings_data

def save_embeddings_to_db(embeddings_data: list):
    """Save the list of embeddings to the MySQL database."""
    conn = None
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()
        
        insert_query = """
        INSERT INTO embeddings (song_id, embedding)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE embedding = VALUES(embedding);
        """
        
        saved_count = 0
        for item in tqdm.tqdm(embeddings_data, desc="Saving embeddings to DB"):
            song_id = item["song_id"]
            embedding_vector = item["embedding"]
            
            embedding_json = None
            if embedding_vector is not None:
                embedding_json = json.dumps(embedding_vector)
            
            try:
                cursor.execute(insert_query, (song_id, embedding_json))
                saved_count += 1
            except mysql.connector.Error as e:
                logger.error(f"Error saving embedding for song_id {song_id}: {e}")

        conn.commit()
        logger.info(f"Successfully saved or updated {saved_count} embeddings in the database.")

    except mysql.connector.Error as e:
        logger.error(f"Database error while saving embeddings: {e}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def main():
    logger.info("Script execution started.")
    args = parse_args()
    
    # Ensure API key is available for OpenAI client
    if not args.openai_key:
        logger.error("OpenAI API key not found. Please set OPENAI_API_KEY environment variable or use --openai-key argument.")
        return
        
    client = OpenAI(api_key=args.openai_key)

    if not DB_USER or not DB_PASSWORD:
        logger.error("Database user (DB_USER) or password (DB_PASSWORD) not set in environment variables.")
        return

    create_embeddings_table()

    logger.info("Loading and preparing data from database...")
    songs_df = load_and_prepare_data()

    if songs_df.empty:
        logger.warning("No data to process after loading and preparing. Exiting.")
        return

    logger.info("Generating embeddings...")
    embeddings_list = generate_embeddings(songs_df, client, EMB_MODEL, args.batch_size, args.max_song_tokens)

    if not embeddings_list:
        logger.warning("No embeddings were generated. Exiting.")
        return

    save_embeddings_to_db(embeddings_list)
    logger.info("Successfully generated and saved embeddings to the database.")
    logger.info("Script execution finished.")

if __name__ == "__main__":
    main()