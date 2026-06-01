# Jammu Cause List RAG

A local RAG-based search and question-answering system for Jammu District Court cause-list PDFs.

The project ingests court cause-list PDFs, extracts structured case data, stores it in SQLite, builds semantic search indexes with Chroma, and answers questions using a local Llama model through Ollama.

The app includes:

- FastAPI backend
- React frontend
- SQLite exact search
- Chroma vector search
- Local embeddings with `sentence-transformers`
- Local Llama-based RAG through Ollama
- PDF upload with automatic parsing and indexing
- Dockerized backend and frontend
- Basic backend tests and CI-ready structure

---

## Project status

Current working features:

- Upload new PDFs
- Parse cause-list rows
- Parse detailed case sections
- Search cause-list rows
- Search detailed case records
- Run semantic search
- Ask questions using local Llama
- View results in React frontend
- Run backend and frontend with Docker Compose

---

## Tech stack

### Backend

- Python
- FastAPI
- SQLite
- PyMuPDF
- ChromaDB
- sentence-transformers
- Ollama Python client
- pytest
- ruff

### Frontend

- React
- Vite
- Nginx for Docker frontend serving

### Local LLM

- Ollama
- Llama 3.2

### Containerization

- Docker
- Docker Compose

---

## High-level architecture

```text
PDF files
   |
   v
FastAPI ingestion pipeline
   |
   +--> Extract text from PDFs
   |
   +--> Parse cause-list rows
   |
   +--> Parse detailed case sections
   |
   +--> Store structured data in SQLite
   |
   +--> Build semantic chunks
   |
   +--> Store embeddings in Chroma
   |
   v
Search / Ask APIs
   |
   +--> SQLite exact search
   +--> Chroma semantic search
   +--> Local Llama answer generation through Ollama
   |
   v
React frontend
```

---

## Main features

### 1. PDF upload

Upload new court cause-list PDFs from the frontend or API.

The backend:

- Saves the PDF into `data/raw/`
- Calculates file hash
- Skips duplicate PDFs
- Extracts cause-list rows
- Extracts detailed case data
- Stores parsed data in SQLite
- Adds chunks to the vector index

---

### 2. Exact search

Search structured data using:

- Listing date
- Court number
- Stage
- Advocate
- Party name
- Case reference
- Registration number
- CNR number

Example API:

```text
GET /cases?q=AKASH%20GUPTA
GET /cases?listing_date=20-03-2026
GET /case-details?registration_number=1344%2F2024
```

---

### 3. Semantic search

Search using natural language.

Example:

```text
GET /semantic-search?q=cases%20involving%20POCSO%20and%20FIR%20details
```

---

### 4. Local RAG question answering

Ask questions using local retrieval and local Llama.

Example:

```json
{
  "question": "What is the next hearing date for Complaint/1344/2024?",
  "limit": 10
}
```

The system retrieves relevant SQLite and vector records, sends them to local Llama through Ollama, and returns an answer with sources.

---

## Important privacy note

Do not commit court PDFs, SQLite databases, Chroma vector stores, `.env` files, or model caches.

These files may contain sensitive legal/court data such as:

- Party names
- Advocate names
- CNR numbers
- FIR details
- Case history
- Hearing dates
- Court and judge information

Ignored local data:

```text
data/raw/
data/extracted/
data/processed/*.db
data/vector_store/
data/model_cache/
.env
.env.docker
```

---

## Project structure

```text
jammu-causelist-rag/
│
├── app/
│   ├── api/
│   ├── db/
│   │   └── database.py
│   ├── ingestion/
│   │   ├── cause_list_parser.py
│   │   ├── case_detail_parser.py
│   │   └── ingest_service.py
│   ├── rag/
│   │   ├── llama_rag.py
│   │   └── free_answer_engine.py
│   ├── retrieval/
│   │   ├── chunk_builder.py
│   │   └── vector_store.py
│   └── main.py
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── App.css
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.js
│
├── scripts/
│   ├── extract_text.py
│   ├── quick_search.py
│   ├── ingest_existing_pdfs.py
│   ├── backfill_case_details.py
│   ├── rebuild_vector_index.py
│   └── run_rag_eval.py
│
├── tests/
│   └── test_api_smoke.py
│
├── data/
│   ├── raw/
│   ├── extracted/
│   ├── processed/
│   ├── vector_store/
│   └── eval/
│
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
├── .env.example
├── .env.docker.example
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Requirements

### Required for local Python development

- Python 3.11+
- pip
- virtual environment

### Required for local Llama

- Ollama
- Llama model, for example `llama3.2`

### Required for Docker setup

- Docker
- Docker Compose

### Optional for frontend-only local development

- Node.js
- npm

If Node.js is not installed locally, the frontend can still be built using Docker.

---

## Environment setup

Create local environment file:

```bash
cp .env.example .env
```

Example `.env`:

```bash
APP_ENV=local

OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2

API_HOST=0.0.0.0
API_PORT=8000
```

Create Docker environment file:

```bash
cp .env.docker.example .env.docker
```

Example `.env.docker`:

```bash
APP_ENV=docker

OLLAMA_HOST=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2

API_HOST=0.0.0.0
API_PORT=8000
```

---

## Local Python setup

Create and activate virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install Python dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Ollama setup

Install Ollama separately on your machine.

Pull the model:

```bash
ollama pull llama3.2
```

Check installed models:

```bash
ollama list
```

Test Ollama:

```bash
curl http://localhost:11434/api/tags
```

If Ollama is not running, start it:

```bash
ollama serve
```

---

## Data setup

Put PDFs into:

```text
data/raw/
```

Then run the ingestion pipeline:

```bash
python -m scripts.ingest_existing_pdfs
python scripts/backfill_case_details.py
python scripts/rebuild_vector_index.py
```

This creates or updates:

```text
data/processed/cause_list.db
data/vector_store/chroma/
```

---

## Run backend locally without Docker

Start FastAPI:

```bash
python -m uvicorn app.main:app --reload
```

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

---

## Run frontend locally without Docker

Only needed if Node.js is installed locally.

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

Make sure backend is running at:

```text
http://127.0.0.1:8000
```

---

## Run full app with Docker Compose

Make sure Ollama is running on your host machine first:

```bash
ollama list
```

Then run:

```bash
docker compose build
docker compose up
```

Frontend:

```text
http://127.0.0.1:3000
```

Backend Swagger:

```text
http://127.0.0.1:8000/docs
```

Stop Docker:

```bash
docker compose down
```

Run in background:

```bash
docker compose up -d
```

View logs:

```bash
docker compose logs -f api
docker compose logs -f frontend
```

---

## API endpoints

### Health

```text
GET /health
```

### Documents

```text
GET /documents
POST /documents/upload
```

### Cause-list rows

```text
GET /cases
```

Example:

```text
GET /cases?q=AKASH%20GUPTA
GET /cases?listing_date=20-03-2026
GET /cases?stage=Prosecution%20Evidence
```

### Case details

```text
GET /case-details
GET /case-details/{case_detail_id}
```

Example:

```text
GET /case-details?registration_number=1344%2F2024
GET /case-details?cnr_number=JKJM030067592024
```

### Semantic search

```text
GET /semantic-search
```

Example:

```text
GET /semantic-search?q=warrant%20of%20arrest%20process%20details
```

### Vector index status

```text
GET /vector/status
```

### Llama status

```text
GET /llama/status
```

### Ask

```text
POST /ask
```

Example body:

```json
{
  "question": "What is the next hearing date for Complaint/1344/2024?",
  "limit": 10
}
```

---

## Example questions

Try these from Swagger or the frontend:

```text
What is the next hearing date for Complaint/1344/2024?
```

```text
What are the FIR details for Challan Case/61/2023?
```

```text
Which anticipatory bail applications were listed for report on 20-03-2026?
```

```text
Which case has warrant of arrest process details?
```

```text
Which case was transferred to 1st Additional District and Session Judge Jammu?
```

```text
Find cases involving POCSO and FIR details.
```

---

## Testing

Run backend tests:

```bash
pytest -q
```

Run lint:

```bash
ruff check .
```

Run local check script:

```bash
./scripts/local_check.sh
```

The local check script verifies:

- Backend tests
- Frontend build
- Docker build

---

## Evaluation

If `data/eval/questions.jsonl` is configured, run retrieval evaluation:

```bash
python scripts/run_rag_eval.py --mode retrieve --limit 10
```

Run full local Llama evaluation:

```bash
python scripts/run_rag_eval.py --mode ask --limit 8 --max-cases 3
```

Retrieval eval is faster and does not call Llama.

---

## Docker notes

The Docker setup runs:

```text
api       FastAPI backend
frontend  React frontend served by Nginx
```

Ollama runs outside Docker on the host machine.

From inside Docker, the backend connects to Ollama using:

```text
http://host.docker.internal:11434
```

This is configured in:

```text
.env.docker
```

---

## Common Docker commands

Build:

```bash
docker compose build
```

Start:

```bash
docker compose up
```

Start in background:

```bash
docker compose up -d
```

Stop:

```bash
docker compose down
```

View backend logs:

```bash
docker compose logs -f api
```

View frontend logs:

```bash
docker compose logs -f frontend
```

Run ingestion inside Docker:

```bash
docker compose exec api python -m scripts.ingest_existing_pdfs
docker compose exec api python scripts/backfill_case_details.py
docker compose exec api python scripts/rebuild_vector_index.py
```

---

## Troubleshooting

### `/documents` returns empty

Check that PDFs exist:

```bash
ls data/raw
```

Then run:

```bash
python -m scripts.ingest_existing_pdfs
python scripts/backfill_case_details.py
python scripts/rebuild_vector_index.py
```

If running inside Docker:

```bash
docker compose exec api python -m scripts.ingest_existing_pdfs
docker compose exec api python scripts/backfill_case_details.py
docker compose exec api python scripts/rebuild_vector_index.py
```

---

### `/vector/status` shows count 0

Rebuild the vector index:

```bash
python scripts/rebuild_vector_index.py
```

Or inside Docker:

```bash
docker compose exec api python scripts/rebuild_vector_index.py
```

---

### `/llama/status` fails

Check Ollama on host:

```bash
curl http://localhost:11434/api/tags
```

Check from inside Docker:

```bash
docker compose exec api python - <<'PY'
import urllib.request

url = "http://host.docker.internal:11434/api/tags"

with urllib.request.urlopen(url, timeout=10) as response:
    print(response.read().decode())
PY
```

If it fails, restart Ollama:

```bash
ollama serve
```

Then restart Docker:

```bash
docker compose down
docker compose up
```

---

### Frontend cannot reach backend

Check:

```text
http://127.0.0.1:3000/api/health
```

Expected:

```json
{
  "status": "ok"
}
```

If it fails, check logs:

```bash
docker compose logs -f frontend
docker compose logs -f api
```

---

## GitHub setup

Initialize repo:

```bash
git init
git add .
git status
```

Before committing, make sure these are **not** staged:

```text
data/raw/
data/processed/*.db
data/vector_store/
data/model_cache/
.env
.env.docker
frontend/node_modules/
frontend/dist/
```

Commit:

```bash
git commit -m "Add local RAG backend and React frontend"
```

Add remote:

```bash
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/jammu-causelist-rag.git
git push -u origin main
```

Use a private GitHub repository unless you have removed all private data.

---

## CI/CD

This project includes a GitHub Actions workflow at:

```text
.github/workflows/ci.yml
```

The CI checks:

- Backend install
- Backend tests
- Frontend install
- Frontend build
- Docker image build

CI does not run Ollama and does not require private PDFs.

---

## Current limitations

- The parser is tuned for the current sample court-cause-list PDF format.
- If the court website changes PDF layout, parser updates may be needed.
- Local Llama answers depend on model quality and retrieved context quality.
- The React UI currently shows some results as JSON for simplicity.
- This is an information retrieval tool, not a legal advice system.

---

## Roadmap

Planned improvements:

- Better frontend case-detail display
- Admin button to rebuild vector index
- Better upload progress UI
- Improved parser regression tests
- LangGraph query router
- Role-based access if deployed
- PostgreSQL option for production
- Qdrant option for production vector search
- Better duplicate detection across PDFs
- Better citation formatting in answers

---

## Disclaimer

This project is for searching, summarizing, and retrieving information from uploaded court cause-list documents. It does not provide legal advice.