# MelodyMind

A context-aware music recommendation API using FastAPI, OpenAI, and Elasticsearch.

---

## Run the Project

### 1. **Clone the Repository**

```bash
git clone https://github.com/your-team/melodymind.git
cd melodymind
```

---

### 2. **Set Up Environment Variables**

I will provide you with a .env file. Place the .env file in the root directory of the project.

---

### 3. **Start the Services**

Use Docker Compose to start Elasticsearch and the FastAPI server.

```bash
docker-compose up --build
```

This will:
- Start an Elasticsearch container on `http://localhost:9200`.
- Start the FastAPI server on `http://localhost:5051`.

---

### 4. **Load the Provided Data into Elasticsearch**

1. Place the songs_data.json file in the scripts directory of the project.

2. Run the following command to load the data into Elasticsearch:

   ```bash
   python scripts/load_songs.py
   ```

   This script will:
   - Connect to Elasticsearch at `http://localhost:9200`.
   - Load the songs_data.json file into the `songs` index.

3. Verify the data has been loaded by running:

   ```bash
   curl -X GET "http://localhost:9200/songs/_count"
   ```

   This will return the total number of documents in the `songs` index.

4. To view the fields and their data types in the songs index:

    ```bash
    curl -X GET "http://localhost:9200/songs/_mapping?pretty"
    ```
    
    This will return the mapping of the songs index, including all fields and their types.
---

### 5. **Health Check**

To ensure everything is running correctly, you can check the health of the API by visiting:

```
http://localhost:5051/
```

The response should look like this:

```json
{
  "status": "ok",
  "elasticsearch_connected": true,
  "openai_key_loaded": true
}
```

---

### 6. **Test the API**

1. Open your browser and navigate to the FastAPI documentation at:

   ```
   http://localhost:5051/docs
   ```

2. Use the `/search` endpoint to test the hybrid search functionality. Example payload:

   ```json
   {
     "prompt": "play me a song for driving through the desert at night",
     "size": 3
   }
   ```

3. The response will include a list of songs matching the query, with details such as title, artist, and relevance score.

    ```json
    [
      {
        "title": "That Song Is Driving Me Crazy",
        "artist": "['Tom T. Hall']",
        "score": 64.94453,
        "matched_queries": [
          "keyword_search",
          "prompt_search"
        ],
        "spotify_url": null,
        "youtubemusic_url": null,
        "popularity": 6,
        "release_date": "1995-11-14"
      },
      {
        "title": "Desert Rose",
        "artist": "['Sting']",
        "score": 61.797337,
        "matched_queries": [
          "keyword_search",
          "prompt_search",
          "vector_search"
        ],
        "spotify_url": null,
        "youtubemusic_url": null,
        "popularity": 60,
        "release_date": "1999-01-01"
      },
      {
        "title": "Living For The Night",
        "artist": "['George Strait']",
        "score": 56.214584,
        "matched_queries": [
          "keyword_search",
          "prompt_search",
          "vector_search"
        ],
        "spotify_url": null,
        "youtubemusic_url": null,
        "popularity": 20,
        "release_date": "2009-01-01"
      }
    ]
    ```

---

### How the Search Works

The `/search` endpoint uses a **hybrid search** approach that combines multiple methods to return the most relevant results:

1. **`vector_search`**:
   - Uses OpenAI embeddings to find songs semantically similar to the query.
   - Ideal for capturing the meaning of the query, even if the exact words don't match.

2. **`keyword_search`**:
   - Expands the query into keywords using OpenAI and matches them against song metadata.
   - title has 3 time weights, artist has 2 time weights, and lyrics have 1 time weight.
   - Useful for finding songs with specific terms or phrases.

3. **`prompt_search`**:
   - Matches the original query text against song metadata using Elasticsearch's BM25 algorithm.
   - title has 3 time weights, artist has 2 time weights, and lyrics have 1 time weight.
   - Allows for fuzzy matching (e.g., minor typos or variations).

  The results are ranked based on a combination of these methods, with the most relevant songs appearing first.

---

### 7. **Reindexing Data (Optional)**

If you need to reindex the data (e.g., after modifying the dataset or Elasticsearch mapping), follow these steps:

1. Place the updated dataset (`hits_dataset.csv` and `lyrics.csv`) in the musicoset directory.

2. Run the following command to rebuild the index and generate embeddings:

   ```bash
   docker-compose run data-loader
   ```

   This will:
   - Merge the datasets.
   - Generate OpenAI embeddings.
   - Reindex the data into Elasticsearch.

---

### Notes

- **Embedding Model**: The project uses the `text-embedding-3-small` model (1536-dimensional vectors).
- **Elasticsearch Index**: The index name is `songs` by default. You can change this in the .env file if needed.
- **CORS Configuration**: Update the `CORS_ORIGINS` variable in the .env file to allow requests from specific frontend domains.

---

### Troubleshooting

- **Elasticsearch Connection Issues**:
  - Ensure Elasticsearch is running on `http://localhost:9200`.
  - Check the logs of the Elasticsearch container:
    ```bash
    docker logs melodymind_elasticsearch
    ```

- **FastAPI Server Issues**:
  - Ensure the FastAPI server is running on `http://localhost:5051`.
  - Check the logs of the FastAPI container:
    ```bash
    docker logs melodymind_api
    ```

- **Data Loading Issues**:
  - Ensure the songs_data.json file is correctly formatted and placed in the scripts directory.
  - Check for errors in the `load_songs.py` script output.
