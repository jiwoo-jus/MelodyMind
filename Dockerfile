FROM python:3.10-slim

WORKDIR /app

COPY app/ ./app/
COPY .env .env
COPY wait-for-elasticsearch.sh /wait-for-elasticsearch.sh

# Make the script executable
RUN chmod +x /wait-for-elasticsearch.sh

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir fastapi uvicorn openai "elasticsearch>=8.0.0,<9.0.0" python-dotenv

# We'll use the script in docker-compose, the CMD here will be overridden
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5051"]