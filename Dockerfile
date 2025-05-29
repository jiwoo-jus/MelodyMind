FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Set PYTHONPATH so Python can find the modules
ENV PYTHONPATH "${PYTHONPATH}:/app"

# Copy application code (local app/ directory to container's /app/ directory)
COPY app/ .

# Copy the .env file
COPY .env .

# Copy the wait-for-elasticsearch script
COPY wait-for-elasticsearch.sh /wait-for-elasticsearch.sh

# Make the script executable
RUN chmod +x /wait-for-elasticsearch.sh

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# RUN pip install --no-cache-dir fastapi uvicorn openai "elasticsearch>=8.0.0,<9.0.0" python-dotenv pandas \
#     mysql-connector-python tqdm requests numpy

# Update the pip install line
RUN pip install --no-cache-dir fastapi uvicorn openai "elasticsearch>=8.0.0,<9.0.0" python-dotenv pandas \
    mysql-connector-python sqlalchemy pymysql tqdm requests numpy

# The CMD here will be overridden by docker-compose
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5051"]