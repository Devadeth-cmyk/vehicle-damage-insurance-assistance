# RAG pipeline

This pipeline indexes the insurance PDFs in the repository `data/` folder and
serves policy search and chat endpoints. The scripts live under
`backend/rag_pipeline/scripts`; generated text, chunks, and the ChromaDB index
live under the repository-level `processed/` folder.

## Install dependencies

From the repository root in PowerShell:

```powershell
cd backend
.\venv\Scripts\python.exe -m pip install -r rag_pipeline\requirements-rag.txt
cd rag_pipeline
```

The RAG settings load `backend/.env`. Set `GROQ_API_KEY` there to enable model
responses; retrieval still works without it. Never put a real API key in an
`.env.example` file or commit `.env`.

## Build or rebuild the knowledge base

Run these commands from `backend/rag_pipeline`:

```powershell
..\venv\Scripts\python.exe scripts\extract_text.py
..\venv\Scripts\python.exe scripts\clean_text.py
..\venv\Scripts\python.exe scripts\chunk_text.py
..\venv\Scripts\python.exe scripts\build_vector_db.py
..\venv\Scripts\python.exe scripts\evaluate_retrieval.py --per-company
```

The first run may download the `all-MiniLM-L6-v2` embedding model. Building the
index replaces the `insurance_policies` collection in `processed/vector_db`.

## Run the API

From `backend/rag_pipeline`:

```powershell
..\venv\Scripts\python.exe -m uvicorn scripts.app:app --host 127.0.0.1 --port 8100
```

Open `http://127.0.0.1:8100/docs` for interactive API testing. The main routes
are `GET /health`, `GET /companies`, `POST /search`, and `POST /chat`.

Example search request:

```json
{"question":"What documents are required for a claim?","top_k":5,"company":"ICICI Lombard General Insurance"}
```

`POST /chat` accepts a question, an optional insurer, and optional prior turns.
It responds with an answer, sources, mode (`llm`, `retrieval_only`, or
`no_context`), and model information.
