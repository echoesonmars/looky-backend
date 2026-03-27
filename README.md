# Looky Backend

Monorepo with two services:

| Service | Stack | Role |
|--------|--------|------|
| [node/](node/) | Express + TypeScript | Main HTTP API, items, optional gateway to Python |
| [python/](python/) | FastAPI | ML / heavy compute endpoints (extend here) |

## Node.js (`node/`)

```bash
cd node
npm install
cp .env.example .env
npm run dev
```

Default: [http://localhost:3001](http://localhost:3001)

- `GET /api/health` — Node health
- `GET /api/items` — placeholder list
- `GET /api/services` — Node + Python reachability (set `PYTHON_SERVICE_URL` in `.env`)

Deploy this folder as a separate Vercel project (see [node/vercel.json](node/vercel.json)).

## Python / FastAPI (`python/`)

```bash
cd python
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Default: [http://localhost:8000](http://localhost:8000)

- `GET /api/health` — Python health
- `GET /api/items` — placeholder (Python-side)

Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Running both locally

1. Terminal A: `cd python && uvicorn app.main:app --reload --port 8000`
2. Terminal B: `cd node &&` set `PYTHON_SERVICE_URL=http://localhost:8000` in `.env`, then `npm run dev`
3. Open `GET http://localhost:3001/api/services` to verify both.
