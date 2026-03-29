import base64
import io
import os
from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

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

# ── Lazy model singleton ───────────────────────────────────────────
_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        from app.catvton.pipeline import CatVTONPipeline
        _pipeline = CatVTONPipeline()
    return _pipeline


# ── Request / Response schemas ─────────────────────────────────────
class TryOnRequest(BaseModel):
    person_b64: str          # base64-encoded person image (PNG/JPEG)
    garment_url: str | None = None   # URL to fetch garment from
    garment_b64: str | None = None   # OR base64-encoded garment image
    category: str = "top"            # top | outer | bottom | shoes
    landmarks: list[list[float]] = []  # 33 x [x, y, z, vis] normalized 0-1
    width: int = 384
    height: int = 512
    num_steps: int = 25
    guidance_scale: float = 2.5
    seed: int = 42


class TryOnResponse(BaseModel):
    result_b64: str          # base64-encoded result PNG
    device: str


def _decode_b64_image(b64: str) -> Image.Image:
    data = b64.split(",", 1)[-1]  # strip data:image/...;base64, prefix if present
    return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")


def _fetch_image(url: str) -> Image.Image:
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


def _encode_pil_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ── Endpoints ──────────────────────────────────────────────────────
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "OK", "service": "looky-python", "message": "Looky FastAPI is running"}


@app.get("/api/items")
def items() -> dict[str, list]:
    return {"items": [], "source": "python"}


@app.post("/api/tryon", response_model=TryOnResponse)
def tryon(req: TryOnRequest) -> Any:
    """Virtual try-on: person photo + garment → result image (CatVTON, ICLR 2025)."""
    # Decode person image
    try:
        person_img = _decode_b64_image(req.person_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid person_b64: {e}")

    # Decode garment image
    try:
        if req.garment_b64:
            garment_img = _decode_b64_image(req.garment_b64)
        elif req.garment_url:
            garment_img = _fetch_image(req.garment_url)
        else:
            raise HTTPException(status_code=400, detail="Provide garment_url or garment_b64")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not load garment image: {e}")

    # Generate mask from landmarks
    from app.catvton.image_utils import generate_clothing_mask, resize_and_crop
    if req.landmarks and len(req.landmarks) >= 29:
        mask_img = generate_clothing_mask(req.landmarks, req.category, person_img.width, person_img.height)
    else:
        # Fallback: upper 60% of image for tops, lower 60% for bottoms
        mask_img = Image.new("L", person_img.size, 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask_img)
        w, h = person_img.size
        if req.category in ("top", "outer"):
            draw.rectangle([0, int(h * 0.1), w, int(h * 0.65)], fill=255)
        elif req.category == "bottom":
            draw.rectangle([0, int(h * 0.45), w, h], fill=255)
        else:
            draw.rectangle([0, 0, w, h], fill=255)

    # Load model (lazy, first call takes a while)
    try:
        pipeline = get_pipeline()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Model load failed: {e}")

    # Run inference
    try:
        result = pipeline(
            person_image=person_img,
            garment_image=garment_img,
            mask_image=mask_img,
            num_inference_steps=req.num_steps,
            guidance_scale=req.guidance_scale,
            height=req.height,
            width=req.width,
            seed=req.seed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")

    result_b64 = _encode_pil_to_b64(result)
    return TryOnResponse(result_b64=result_b64, device=pipeline.device)
