# Campus Customs

A Yale merchandise storefront (React + Vite + TypeScript) with a PydanticAI
shopping-assistant chat agent (FastAPI backend).

## Repo layout

```
hw4/
├── AI_prompts.md          # log of every prompt used to build this project
├── requirements.txt       # backend (Python) dependencies
├── .env.example           # template for backend/.env - fill in and rename
├── frontend/              # Vite + React + TypeScript app
├── backend/
│   ├── main.py             # FastAPI app: routes, DB access, accounts
│   ├── agent.py            # agent.py / tools.py / models.py / prompts/prompt.md
│   ├── tools.py            #   are the agent itself - see below
│   ├── models.py
│   ├── security.py         # password hashing (used by main.py)
│   └── prompts/prompt.md
└── output/                 # harness.md, design.md, usability.md, app_check.html, audit_trail.json
```

The agent is deliberately kept to four files under `backend/`:
`prompts/prompt.md` (system prompt), `agent.py` (wiring), `tools.py` (what it
can do), and `models.py` (the Pydantic types it and the API share).

## Data pack (not in this repo)

The product database and images aren't committed here (see `.gitignore`).
Before running the app, place the data pack at the repo root so it sits next
to `backend/` and `frontend/`:

```
hw4/
└── data/
    ├── campus_customs.db
    └── products/            # product images referenced by the catalogue
```

## 1. Configure the backend

```bash
cp .env.example backend/.env
```

Edit `backend/.env` and fill in:

- `OPENAI_API_KEY` — your key for the OpenAI-compatible endpoint
- `OPENAI_BASE_URL` — e.g. `https://api.portkey.ai/v1`
- `OPEN_AI_MODEL` — the model name to request through that endpoint

## 2. Run the backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate      # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```

The API is now at `http://localhost:8000` (interactive docs at `/docs`).

## 3. Run the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (`http://localhost:5173` by default). The dev
server proxies `/api` and product image requests to the backend on `:8000`.

## Notes

- `output/audit_trail.json` is an append-only log of agent activity (tool
  calls, args/results, stop reason) written by the backend as it runs.
- `output/app_check.html` is a standalone report (double-click to open) with
  screenshots proving three core features work against the real database.
