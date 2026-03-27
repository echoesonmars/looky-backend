import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Looky ML / Python API", version="1.0.0")

_origins_raw = os.getenv("CORS_ORIGINS", "*")
_origins = [o.strip() for o in _origins_raw.split(",") if o.strip()] or ["*"]
_use_star = len(_origins) == 1 and _origins[0] == "*"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _use_star else _origins,
    allow_credentials=not _use_star,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "OK", "service": "looky-python", "message": "Looky FastAPI is running"}


@app.get("/api/items")
def items() -> dict[str, list]:
    """Placeholder: ML-heavy or async tasks can live here later."""
    return {"items": [], "source": "python"}
