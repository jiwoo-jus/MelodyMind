Collecting workspace information# MelodyMind Project Setup Guide

Based on your workspace, I'll explain how to set up and run the MelodyMind project with MySQL integration.

## Prerequisites

- MySQL server (download from here => https://dev.mysql.com/downloads/mysql/) with `musicoset` database already set up
- Docker is installed and running

## Setup Steps

### 1. Setup MySQL Database

- Install MySQL according to your operating system
- Download the `musicoset_dump.sql` file from the Google Drive link
- Import the database:
  ```bash
  mysql -u root -p < musicoset_dump.sql
   ```
- Verify the import was successful:
   ```bash
   mysql -u root -p -e "USE musicoset; SHOW TABLES;"
   ```

### 2. Setup Conda Environment

#### Option 1: For new installations 

Create a conda environment using the environment file:

```bash
# Create conda environment
conda create --name melodymind python=3.10
```

#### Option 2: For existing environment

If you already have a 'melodymind' environment, update it:

```bash
# First deactivate if it's active
conda deactivate
# Then update the environment
conda env update -f environment.yml --prune
```

#### Don't forget to activate the environment:

Activate the conda environment

```bash
conda activate melodymind
```

### 3. Configure Environment Variables

Ensure your .env file contains these essential variables:

```
ELASTICSEARCH_HOST=http://elasticsearch:9200
ELASTICSEARCH_INDEX=songs
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
PORT=5051
UVICORN_RELOAD=True
CORS_ORIGINS=http://localhost,http://localhost:3000,http://localhost:5051
DB_HOST="host.docker.internal"
DB_USER=your_mysql_username # ex, "root"
DB_PASSWORD=your_mysql_password
DB_NAME="musicoset"
```

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

### 5. Test the API

Once everything is running, test the API:

visit `http://localhost:5051/docs` in your browser to use the Swagger UI.

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
```

#### Common Queries for Inspection
```sql
-- Count records in tables
SELECT COUNT(*) FROM songs;
SELECT COUNT(*) FROM embeddings;

-- Check for songs with missing embeddings
SELECT s.song_id, s.song_name 
FROM songs s 
LEFT JOIN embeddings e ON s.song_id = e.song_id 
WHERE e.embedding IS NULL;

-- View sample data
SELECT * FROM songs LIMIT 5;
SELECT * FROM artists LIMIT 5;
```