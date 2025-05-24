# MelodyMind

A context-aware music recommendation API using Elasticsearch.

**Important Prerequisites (Assumed for all future instructions, even if not explicitly stated in this README):**

* **Activate Conda Environment:**
    * `conda activate MelodyMind`
    * If newly pulled code imports new libraries, you must install them within this activated environment using `conda install` or `pip install`.
    * Be aware that package names can differ from import names. Don't just type `conda install xx` if you see `import xx`.
    * Search for `conda install xx` on Google and use the command provided by Anaconda.org. If a Conda version isn't available, use the `pip install` command from PyPI.
* **`.env` File:**
    * If you've newly cloned the repository, copy the `.env` file into the root folder.
    * This file contains environment configurations, including sensitive information that should not be exposed publicly. Therefore, it's not uploaded to GitHub and is shared separately.
* **Docker:**
    * Ensure Docker is running.

**Please Read the Following:**

* It's not feasible to list every basic command for the terminal, Git, and Conda in this README. If you're unfamiliar with them, please use Google or ChatGPT to find the necessary commands.
* If you encounter an error, read the error message carefully and try to understand the cause. Instead of blindly copying and pasting code from this README, think about its meaning and modify commands appropriately for your environment.
    * For example, if the README says to put data in the `scripts` folder, but you've saved your data in `data/musicoset`, that's fine. Just consider which part of the code references this data and change the relevant line specifying the data path.
    * If you decide to follow the README, place the data in the `scripts` folder and set the data path in `scripts/update_songs.py` to `"songs_data.json"`. If you choose to use the `data/musicoset` folder, update the data reference in `scripts/update_songs.py` to an absolute path.
    * The same applies to terminal commands. If the README says `python scripts/update_songs.py`, but your terminal is already in the `scripts` folder, you can simply type `python update_songs.py`.
    * Of course, clean coding is important, and when pushing to the remote repository, both you and I should avoid absolute paths and use relative paths with clear README instructions. However, an imperfect setup shouldn't prevent you from getting the environment running.
* Ultimately, you need to understand this code, not just run it. This will allow you to adapt to various situations and proceed with further development. It will also save me time spent creating such detailed READMEs.
    * I know you're all capable. Please invest a little more time. We have an excellent teacher in ChatGPT.
* Starting next week, I hope we can spend less time on environment setup. If you've tried and failed, don't just come to me with the problem. Try to solve it yourself, ask for help if you're stuck, and ultimately, arrive with the setup completed.
    * There might be incorrect or unclear parts in my README. If you discover such issues while debugging, please share them in the general Discord chat so others don't waste time on the same problem.
    * If someone is stuck and not making progress, they should first try to solve it independently, but also share the issue on Discord and tackle it together. Even if you don't know the exact answer, looking into a colleague's problem and trying to solve it together can be beneficial.
* I don't think the frontend team needs to understand every aspect of the backend code and keep pace with its development. Of course, if they understand both frontend and backend content by the end, it will significantly enhance their skills, but as team members, their primary responsibility lies in frontend implementation.
* Backend team should feel responsible for helping the frontend team with their environment setup. Also, since there are twice as many people on the backend, they should always develop the API first and provide a refined, detailed API specification to the frontend team. It's not ideal for the frontend to implement interface first and then have to refactor code after the API documentation is released.

---

## Run the Project

### **Clone the Repository**

**Case 1:** Pull or checkout the `Jiwoo` remote branch into your local branch from the existing `MelodyMind` repository.

**Case 2:** (If there's a risk of conflicts with existing work) Clone the repository anew from the `Jiwoo` branch. In this case, rename your existing `MelodyMind` repository or clone the new repository with a different name.

```bash
git clone -b Jiwoo https://github.com/jiwoo-jus/MelodyMind
```

### **Set Up Environment Variables**

Place the `.env` file in the root directory of the project.

### Activate Conda Environment

If you don't have the `MelodyMind` Conda environment:
```bash
conda env create -f environment.yml
```

If you already have the environment set up, activate it:
```bash
conda activate MelodyMind
```

### **Start the Services**

Use Docker Compose to start Elasticsearch and the FastAPI server.
```bash
docker-compose up --build
```

### **Load the Provided Data into Elasticsearch**

1.  Place `songs_data.json` and `lyrics.csv` in the `data/musicoset` directory of the project.
2.  Run the following command to load the data and create the Elasticsearch index:

```bash
python scripts/update_songs.py
```

#### Rebuild Services After Index Update

If you update the index, you'll need to rebuild and restart the services:
```bash
docker-compose down
docker-compose up --build
```

### (Optional) Verify the Data Has Been Loaded

This will return the total number of documents in the `songs` index.
```bash
curl -X GET "http://localhost:9200/songs/_count"
```

### (Optional) View Index Mapping

This will return the mapping of the `songs` index, including all fields and their types.
```bash
curl -X GET "http://localhost:9200/songs/_mapping?pretty"
```

### (Optional) **Health Check**

To ensure everything is running correctly, you can check the health of the API by visiting:
`http://localhost:5051/`

The response should look like this:
```json
{
  "status": "ok",
  "elasticsearch_connected": true,
  "openai_key_loaded": true
}
```

### **Test the API**

1.  Open your browser and navigate to the FastAPI documentation at:
`http://localhost:5051/docs`
2.  Use the `/search` endpoint to test the hybrid search functionality.

Example payload:
```json
{
  "prompt": "play me a song for driving through the desert at night",
  "size": 3
}
```

The response will include a list of songs matching the query, with details such as title, artist, and relevance score.
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

## Code Overview

### How the Search Works

The `/search` endpoint uses a **hybrid search** approach that combines multiple methods to return the most relevant results:

1.  **`vector_search`**:
    * Uses OpenAI embeddings to find songs semantically similar to the query.
    * Ideal for capturing the meaning of the query, even if the exact words don't match.

2.  **`keyword_search`**:
    * Expands the query into keywords using OpenAI and matches them against song metadata.
    * The title has a 3x weight, the artist has a 2x weight, and lyrics have a 1x weight.
    * Useful for finding songs with specific terms or phrases.

3.  **`prompt_search`**:
    * Matches the original query text against song metadata using Elasticsearch's BM25 algorithm.
    * The title has a 3x weight, the artist has a 2x weight, and lyrics have a 1x weight.
    * Allows for fuzzy matching (e.g., minor typos or variations).

The results are ranked based on a combination of these methods, with the most relevant songs appearing first.

### Notes

* **Embedding Model**: Currently, we are using the `text-embedding-3-small` model (1536-dimensional vectors).
* **Elasticsearch Index**: The index name is `songs` by default. You can change this in the `.env` file if needed.
* **CORS Configuration**: Update the `CORS_ORIGINS` variable in the `.env` file to allow requests from specific frontend domains.
* `build_songs_index.py`: This script is used to build the Elasticsearch index for the songs data. **Do not run this script experimentally, as it will generate embeddings for all songs using the embedding model, incurring costs.**