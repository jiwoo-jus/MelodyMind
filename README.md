# MelodyMind

A context-aware music recommendation API using FastAPI, OpenAI, and Elasticsearch.

## Quick Start (Docker)

### 1. Clone the repository

```bash
git clone https://github.com/your-team/melodymind.git
cd melodymind
````

### 2. Set up environment variables

Create a `.env` file in the project root directory. I (Jiwoo) will provide the content.

Use the `environment.yml` file to create the Conda environment:

```bash
conda env create -f environment.yml
conda activate melodymind
```

### 3. Start the app

```bash
docker-compose up --build
```

This will start both the FastAPI server and Elasticsearch.

If the app has already been built and you just want to start it again, use:

```bash
docker-compose up
```

## How to Test

Go to:

```
http://localhost:5051/docs
```

Use the `/api/search` endpoint with a POST request. Example payload:
```json
{
  "prompt": "play me a song for driving through the desert at night"
}
```

Only two songs are currently available. Please test with prompts related to:

* driving, night, desert
* beach, wave, chill
