# MelodyMind Project Setup Guide

## Prerequisites

- Clone this repository with the command:
```bash
git clone -b Jiwoo https://github.com/jiwoo-jus/MelodyMind.git melodymind_new
```
- Docker is installed and running

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
CORS_ORIGINS=http://localhost,http://localhost:3000,http://localhost:5051
DB_HOST="host.docker.internal"
DB_USER="root"
DB_PASSWORD=
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

If some services fail to start, you can check the logs in docker container.

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
```