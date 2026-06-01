
# Jammu Cause List RAG



Local RAG system for Jammu District Court cause-list PDFs.



## Features



- PDF upload

- Cause-list table parsing

- Detailed case parsing

- SQLite exact search

- Chroma semantic search

- Local Llama RAG through Ollama

- React frontend

- Dockerized backend and frontend



## Local requirements



- Python 3.11+

- Docker + Docker Compose

- Ollama with llama3.2



## Local Python setup



```bash

python -m venv .venv

source .venv/bin/activate

python -m pip install -r requirements.txt

