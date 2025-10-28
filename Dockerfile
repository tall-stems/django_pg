# Dockerfile for Celery Worker (optional)
# Note: You can run the worker directly with the management command instead
# This is only needed if you want to run the worker in Docker

FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run celery worker
CMD ["celery", "-A", "playground", "worker", "--loglevel=info"]
