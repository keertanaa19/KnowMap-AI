# Reuse existing KnowMap AI image with installed AI/ML dependencies
FROM ishwari29/knowmap-app:latest

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5000 \
    DATABASE_PATH=/app/data/users.db

# Set working directory
WORKDIR /app

# Install only missing Flask dependencies
# PyTorch, spaCy, NumPy, scikit-learn and SentenceTransformers
# are already installed in the existing image
RUN pip install --no-cache-dir --timeout 300 --retries 5 \
    Flask==3.0.3 \
    Werkzeug==3.0.3 \
    PyJWT==2.8.0 \
    flask-cors==4.0.1 \
    gunicorn==23.0.0

# Verify existing AI/ML dependencies
RUN python -c "import torch, spacy, sentence_transformers, sklearn, numpy; spacy.load('en_core_web_sm'); print('AI dependencies verified successfully')"

# Create persistent database directory
RUN mkdir -p /app/data

# Copy current KnowMap AI project files
COPY . /app/

# Copy existing database if available
RUN if [ -f /app/users.db ]; then cp /app/users.db /app/data/users.db; fi

# Persistent database storage
VOLUME ["/app/data"]

# Application port
EXPOSE 5000

# Disable any inherited healthcheck from the old image
HEALTHCHECK NONE

# Start Flask application using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app:app"]