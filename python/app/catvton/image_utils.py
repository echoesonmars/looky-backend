"""Image processing utilities for CatVTON inference."""
import numpy as np
import torch
from PIL import Image, ImageDraw


def numpy_to_pil(images: np.ndarray) -> list:
    if images.ndim == 3:
        images = images[None, ...]
    images = (images * 255).round().astype("uint8")
    return [Image.fromarray(img) for img in images]


def prepare_image(image: Image.Image) -> torch.Tensor:
    """PIL RGB → (1, 3, H, W) tensor in [-1, 1]."""
    img = np.array(image.convert("RGB")).astype(np.float32)
    img = img[None].transpose(0, 3, 1, 2)  # (1, 3, H, W)
    return torch.from_numpy(img) / 127.5 - 1.0


def prepare_mask_image(mask: Image.Image) -> torch.Tensor:
    """PIL L-mode mask → (1, 1, H, W) binary tensor in [0, 1]."""
    arr = np.array(mask.convert("L")).astype(np.float32) / 255.0
    arr = (arr > 0.5).astype(np.float32)
    return torch.from_numpy(arr[None, None])  # (1, 1, H, W)


def resize_and_crop(image: Image.Image, size: tuple) -> Image.Image:
    """Center-crop to target aspect ratio, then resize."""
    w, h = size
    iw, ih = image.size
    target_aspect = w / h
    src_aspect = iw / ih
    if src_aspect > target_aspect:
        new_w = int(ih * target_aspect)
        left = (iw - new_w) // 2
        image = image.crop((left, 0, left + new_w, ih))
    else:
        new_h = int(iw / target_aspect)
        top = (ih - new_h) // 2
        image = image.crop((0, top, iw, top + new_h))
    return image.resize((w, h), Image.LANCZOS)


def resize_and_padding(image: Image.Image, size: tuple) -> Image.Image:
    """Resize preserving aspect ratio, pad remaining area with gray."""
    w, h = size
    iw, ih = image.size
    scale = min(w / iw, h / ih)
    new_w, new_h = int(iw * scale), int(ih * scale)
    image = image.resize((new_w, new_h), Image.LANCZOS)
    bg_color = (128, 128, 128) if image.mode == "RGB" else 0
    canvas = Image.new(image.mode, (w, h), bg_color)
    canvas.paste(image, ((w - new_w) // 2, (h - new_h) // 2))
    return canvas


def generate_clothing_mask(
    landmarks: list,
    category: str,
    image_w: int,
    image_h: int,
) -> Image.Image:
    """Generate a white polygon mask for the clothing region from MediaPipe landmarks.

    landmarks: list of 33 items, each [x, y, z, visibility] normalized 0-1.
    category: 'top' | 'outer' | 'bottom' | 'shoes' | other
    """
    mask = Image.new("L", (image_w, image_h), 0)
    draw = ImageDraw.Draw(mask)

    def pt(idx: int):
        lm = landmarks[idx]
        return (int(lm[0] * image_w), int(lm[1] * image_h))

    def expand(point, cx, cy, factor=1.28):
        return (int(cx + (point[0] - cx) * factor), int(cy + (point[1] - cy) * factor))

    if category in ("top", "outer"):
        ls, rs = pt(11), pt(12)  # shoulders
        lh, rh = pt(23), pt(24)  # hips
        le, re = pt(13), pt(14)  # elbows

        cx = (ls[0] + rs[0] + lh[0] + rh[0]) // 4
        cy = (ls[1] + rs[1] + lh[1] + rh[1]) // 4

        pts = [
            expand(ls, cx, cy, 1.35),
            expand(le, cx, cy, 1.3),
            expand(rs, cx, cy, 1.35),
            expand(re, cx, cy, 1.3),
            expand(rh, cx, cy, 1.2),
            expand(lh, cx, cy, 1.2),
        ]
        draw.polygon(pts, fill=255)

    elif category == "bottom":
        lh, rh = pt(23), pt(24)  # hips
        lk, rk = pt(25), pt(26)  # knees
        la, ra = pt(27), pt(28)  # ankles

        cx = (lh[0] + rh[0] + la[0] + ra[0]) // 4
        cy = (lh[1] + rh[1] + la[1] + ra[1]) // 4

        pts = [
            expand(lh, cx, cy, 1.25),
            expand(rh, cx, cy, 1.25),
            expand(rk, cx, cy, 1.2),
            expand(lk, cx, cy, 1.2),
            expand(ra, cx, cy, 1.15),
            expand(la, cx, cy, 1.15),
        ]
        draw.polygon(pts, fill=255)

    elif category == "shoes":
        la, ra = pt(27), pt(28)  # ankles
        lf, rf = pt(31), pt(32)  # feet

        cx = (la[0] + ra[0]) // 2
        cy = (la[1] + ra[1]) // 2

        pts = [
            expand(la, cx, cy, 1.4),
            expand(ra, cx, cy, 1.4),
            expand(rf, cx, cy, 1.3),
            expand(lf, cx, cy, 1.3),
        ]
        draw.polygon(pts, fill=255)

    else:
        draw.rectangle([0, 0, image_w, image_h], fill=255)

    return mask
