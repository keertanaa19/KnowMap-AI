FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5000 \
    DATABASE_PATH=/app/data/users.db

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-cache NLP and SentenceTransformer models at build time for offline readiness
RUN python -m spacy download en_core_web_sm
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Ensure data persistence directory exists
RUN mkdir -p /app/data

# Copy application source code
COPY . .

# Initialize data volume with existing database if available
RUN if [ -f /app/users.db ]; then cp /app/users.db /app/data/users.db; fi

# Declare persistent volume
VOLUME ["/app/data"]

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Start production server with Gunicorn (1 worker + 4 threads preserves shared PyTorch memory & in-memory cache)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app:app"]
