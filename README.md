# MelodyMind Project Setup Guide

---

## **Update: Music Links Table Addition (2025-06-11)**

> **Note:** This update assumes that all the setup steps below (in the "Prerequisites" and "Setup Steps" sections) have been completed successfully.

### For the person who adds the table (currently Jiwoo, but refer to this section if future fetch code or data updates are needed):

1. **Update your conda environment:**
```bash
conda install conda-forge::ytmusicapi
```

2. **Export only the new table structure and data:**
```bash
# Export the table structure
mysqldump -u root -p --no-data musicoset melodymind_song_links > melodymind_song_links_structure.sql

# Export the table data
mysqldump -u root -p --no-create-info musicoset melodymind_song_links > melodymind_song_links_data.sql

# Or export both structure and data together
mysqldump -u root -p musicoset melodymind_song_links > melodymind_song_links_complete.sql
```

3. **Share the SQL file(s) with team members** via Google Drive (https://drive.google.com/drive/folders/1_lQVDc7gWdWzdMrPOCqBHAHkSwgz5iyK).

4. **Run the following query to verify the table's data (for validation purposes):**
```sql
SELECT 
    COUNT(*) AS total,
    SUM(spotify_url IS NULL) AS sp_null,
    ROUND(SUM(spotify_url IS NULL) / COUNT(*) * 100, 2) AS sp_null_pct,
    SUM(spotify_url IS NOT NULL) AS sp_not_null,
    ROUND(SUM(spotify_url IS NOT NULL) / COUNT(*) * 100, 2) AS sp_not_null_pct,
    SUM(youtube_music_url IS NULL) AS yt_null,
    ROUND(SUM(youtube_music_url IS NULL) / COUNT(*) * 100, 2) AS yt_null_pct,
    SUM(youtube_music_url IS NOT NULL) AS yt_not_null,
    ROUND(SUM(youtube_music_url IS NOT NULL) / COUNT(*) * 100, 2) AS yt_not_null_pct
FROM melodymind_song_links;
```

---

### For team members who need to update their database and code:

1. **Download the shared SQL file(s)** to your project root directory.

2. **Import the new table:**
```bash
# If you received the complete file (structure + data):
mysql -u root -p musicoset < melodymind_song_links_complete.sql

# Or if you received separate files:
mysql -u root -p musicoset < melodymind_song_links_structure.sql
mysql -u root -p musicoset < melodymind_song_links_data.sql
```

3. **Verify the import was successful:**
```bash
mysql -u root -p -e "USE musicoset; SHOW TABLES;"
mysql -u root -p -e "USE musicoset; DESCRIBE melodymind_song_links;"
mysql -u root -p -e "
USE musicoset;
SELECT 
    s.song_id, 
    s.song_name, 
    s.artists, 
    a.name AS album_name, 
    l.spotify_url, 
    l.youtube_music_url 
FROM 
    songs s 
LEFT JOIN 
    tracks t ON s.song_id = t.song_id 
LEFT JOIN 
    albums a ON t.album_id = a.album_id 
LEFT JOIN 
    melodymind_song_links l ON s.song_id = l.song_id 
WHERE 
    l.spotify_url IS NOT NULL 
    AND l.youtube_music_url IS NOT NULL 
    AND LOWER(s.song_name) LIKE LOWER('%Already Callin\' You Mine%')  
LIMIT 3;
"
```

4. **Update your codebase and Restart the services:**
```bash
# After pulling the latest changes from the `Jiwoo` branch, make sure to rebuild the Docker containers:
docker-compose up --build
```


---

## Prerequisites

- Clone this repository with the command:
```bash
git clone -b Jiwoo https://github.com/jiwoo-jus/MelodyMind.git melodymind_new
```
- Docker is installed and running

---

## Setup Steps

### 1. Setup MySQL Database

1.1. Install MySQL according to your operating system (download from here => https://dev.mysql.com/downloads/mysql/)

1.2. Download the `musicoset_dump.sql` and place it in the root of your cloned repository (`melodymind_new` directory). (download from here => https://drive.google.com/drive/folders/1_lQVDc7gWdWzdMrPOCqBHAHkSwgz5iyK)

1.3. Open MySQL and create the database:

- Connect to MySQL:
```bash
mysql -u root -p
```
- Create the database:
```bash
CREATE DATABASE IF NOT EXISTS musicoset;
```
- Verify the database was created:
```bash
SHOW DATABASES;
```
- Exit MySQL:
```bash
EXIT;
```

1.4. Import the database dump into MySQL. Make sure you are in the `melodymind_new` directory where `musicoset_dump.sql` is located.

- Import the database:
```bash
mysql -u root -p musicoset < musicoset_dump.sql
```
- Verify the import was successful:
```bash
mysql -u root -p -e "USE musicoset; SHOW TABLES;"
```

### 2. Setup Conda Environment

#### Option 1: For who wants to create a environment from scratch

```bash
# First deactivate if it's active
conda deactivate
# Then remove the existing environment
conda remove --name melodymind --all
conda remove --name MelodyMind --all
# Then, create a new environment using the provided `environment.yml` file. Ensure you are in the `melodymind_new` directory:
conda env create -f environment.yml
# Activate the newly created environment
conda activate MelodyMind
```

#### Option 2: For who wants to update the existing environment

```bash
# First deactivate if it's active
conda deactivate
# Then update the environment
conda env update -f environment.yml --prune
# Activate the updated environment
conda activate MelodyMind
```

#### Don't forget to activate the environment !! whenever you work on the project !! :

```bash
conda activate MelodyMind
```

### 3. Configure Environment Variables

3.1. Copy and paste the following environment variables into a `.env` file in the root of your project directory (`melodymind_new`):

3.2. Put the OpenAI API key which I shared with you before.

3.3. Put the MySQL root password you set during MySQL installation.

```bash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
ELASTICSEARCH_HOST=http://elasticsearch:9200
ELASTICSEARCH_INDEX=songs
PORT=5051
UVICORN_RELOAD=True
CORS_ORIGINS=http://localhost,http://127.0.0.1:5500,http://localhost:3000,http://localhost:5051
DB_HOST="host.docker.internal"
DB_USER="root"
DB_PASSWORD=
DB_NAME="musicoset"
```

---

### 4. Start the Services

Run the following command to start Elasticsearch, the FastAPI server, and the data loader:
```bash
docker-compose up --build
```

The setup will execute in this order:
1. Elasticsearch container starts first
2. The wait-for-elasticsearch.sh script ensures Elasticsearch is fully running before proceeding
3. The data-loader container runs build_songs_index.py which:
   - Connects to your MySQL database
   - Fetches song data with pre-computed embeddings
   - Creates the Elasticsearch index
   - Loads the data into Elasticsearch
4. FastAPI server starts and exposes the search endpoint at `http://localhost:5051`

If some services fail to start, you can check the logs in docker container.

---

### 5. Test the API

Once everything is running, test the API:

visit `http://localhost:5051/docs` in your browser to use the Swagger UI.

The `/search` endpoint accepts optional filters in the request body:

- `song_name`
- `artist_name`
- `album_name`
- `song_type`
- `release_date`

These fields let you narrow results by song details in addition to the text prompt.


## MySQL Tips

Here are some useful MySQL commands to help you work with the musicoset database:

#### Connecting to MySQL
```bash
mysql -u root -p
# Enter your password when prompted
```

#### Viewing Database Structure
```sql
-- List all databases
SHOW DATABASES;

-- Switch to musicoset database
USE musicoset;

-- List all tables in the current database
SHOW TABLES;

-- View table structure
DESCRIBE songs;
DESCRIBE lyrics;
DESCRIBE embeddings;
DESCRIBE artists;

-- Check collation of each table
SHOW TABLE STATUS LIKE 'songs';
SHOW TABLE STATUS LIKE 'lyrics';
SHOW TABLE STATUS LIKE 'embeddings';
```

#### Common Queries for Inspection
```sql
-- Count records in tables
SELECT COUNT(*) FROM songs;
SELECT COUNT(*) FROM embeddings;

-- Check for some sample data
SELECT s.song_id, s.song_name, s.artists, SUBSTRING(e.embedding, 1, 50) AS embedding_preview
FROM songs s 
LEFT JOIN embeddings e ON s.song_id = e.song_id
WHERE s.song_name like '%Thank%'
LIMIT 3;

-- Check the new music links table
SELECT COUNT(*) FROM melodymind_song_links;
SELECT * FROM melodymind_song_links LIMIT 5;
```