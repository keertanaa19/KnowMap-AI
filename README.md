# KnowMap with AI (Knowledge Mapping & Semantic Search)

An enterprise-ready, interactive Knowledge Graph and Semantic Search application built with Flask, SQLite, spaCy, Sentence Transformers, and Vis.js.

---

## ✨ Features

- 📂 **CSV Dataset Ingestion**: Upload custom triples (`subject,relation,object`) with automatic header detection and deduplication.
- ✍️ **NLP Triple Extraction**: Automatically extract Subject-Predicate-Object relationships from arbitrary English sentences using spaCy dependency parsing.
- 🔎 **Vector Semantic Search**: Search concepts using Sentence Transformers (`all-MiniLM-L6-v2`) with cosine similarity, returning true connected subgraphs.
- 📊 **Analytics Dashboard**: Real-time pipeline monitoring, weekly activity charts (Chart.js), entity counts, and community feedback.
- 🔐 **Authentication & Security**: SQLite-backed user registration, password hashing (`scrypt`), and JWT token authentication.
- 💾 **Persistent Storage**: All triples, users, feedback, and pipeline metrics are stored in SQLite (`users.db`).
- 🐳 **Production Docker Deployment**: Pre-cached NLP & Transformer models for offline container execution and volume-backed data persistence.

---

## 🚀 Quick Start (Local Python)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Run the Application
```bash
python app.py
```
Open your browser and navigate to: **http://127.0.0.1:5000**

---

## 🐳 Docker Deployment

### Option A: Using Docker Compose (Recommended)
This runs the application with a persistent named volume so your data is preserved across container restarts.

```bash
docker compose up --build -d
```
To stop the application:
```bash
docker compose down
```

### Option B: Using Standard Docker CLI

1. **Build the Docker Image**:
   ```bash
   docker build -t knowmap-ai .
   ```

2. **Run the Container with a Persistent Volume**:
   ```bash
   docker run -d -p 5000:5000 -v knowmap_data:/app/data --name knowmap-app knowmap-ai
   ```

3. **Check Container Status & Logs**:
   ```bash
   docker ps
   docker logs -f knowmap-app
   ```

---

## 📁 Project Structure

```text
Knowlegde-mapping-ai-main/
├── app.py                         # Primary Flask backend & UI routes
├── Knowledge_mapping_using_ai.py  # Standalone demo backend (fixed & refactored)
├── Dockerfile                     # Production container spec with pre-cached models
├── docker-compose.yml             # Single-command deployment with volume persistence
├── .dockerignore                  # Filters build context
├── requirements.txt               # Locked Python dependencies (including PyJWT)
├── users.db                       # SQLite database (users, triples, feedback, metrics)
├── semanticapp_sample_triples.csv # Sample knowledge dataset for initial seeding
└── README.md                      # Documentation & deployment guide
```

---

## 🔌 API Endpoints Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/` | `GET` | Landing page |
| `/login` | `GET`, `POST` | User authentication & JWT generation |
| `/signup` | `POST` | New user account creation |
| `/upload` | `GET`, `POST` | Ingest CSV triples dataset |
| `/analyze` | `POST` | NLP sentence triple extraction |
| `/semantic` | `GET` | Semantic search user interface |
| `/search` | `POST` | Vector semantic search over graph nodes |
| `/search_node` | `POST` | Retrieve all triples connected to a node |
| `/dashboard` | `GET` | Analytics dashboard & feedback center |
| `/stats` | `GET` | Real-time counts (triples, nodes, rating) |
| `/metrics` | `GET` | Weekly ingestion pipeline counts |
| `/feedback` | `POST` | Submit star rating (1–5) and comment |
| `/get_feedback` | `GET` | Retrieve community feedback history |
| `/health` | `GET` | Docker healthcheck probe |
