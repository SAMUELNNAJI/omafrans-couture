"""
Dressing room image compositor.

Takes an uploaded dress image and composites it onto a realistic female
body silhouette with dressing-room lighting, fabric tinting and size
scaling — all with Pillow only, no external API required.
"""

from __future__ import annotations

import base64
import io
import logging
import math
import os
import random
from typing import Tuple
import urllib.parse

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

logger = logging.getLogger(__name__)


class ImageGenerationError(RuntimeError):
    """Raised when Gemini cannot return a generated fitting image."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANVAS_W = 720
CANVAS_H = 960

# Body proportions relative to canvas (fraction)
BODY_TOP_FRAC = 0.06      # head top
HEAD_RADIUS_FRAC = 0.065  # head radius relative to canvas width
SHOULDER_FRAC = 0.24      # shoulder y
WAIST_FRAC = 0.52         # waist y
HIP_FRAC = 0.62           # hip y
ANKLE_FRAC = 0.93         # ankle y

# Size scale multipliers (waist/hip width)
SIZE_SCALES = {
    "XS": 0.82,
    "S":  0.91,
    "M":  1.00,
    "L":  1.09,
    "XL": 1.18,
    "2XL": 1.30,
}

# Fabric colour filter (R, G, B shift, brightness)
FABRIC_FILTERS: dict[str, Tuple[float, float, float, float]] = {
    "Premium Gabardine": (1.05, 1.00, 0.95, 1.02),
    "Organic Cotton":    (0.97, 1.02, 0.95, 1.08),
    "Premium Satin":     (1.05, 0.98, 1.05, 0.96),
    "Fine Jersey":       (0.98, 1.00, 0.97, 1.05),
    "Premium Linen":     (1.08, 1.04, 0.94, 0.92),
}

# CSS-like colour tints mapped from frontend filter strings
COLOUR_TINTS: dict[str, Tuple[int, int, int, int]] = {
    # (R, G, B, overlay_alpha 0-255)
    "none":                                                 (0, 0, 0, 0),
    "grayscale(1) brightness(1.9)":                         (255, 252, 244, 30),  # ivory
    "grayscale(1) brightness(1.2)":                         (180, 176, 170, 40),  # stone
    "grayscale(1) brightness(.7)":                          (80, 78, 76, 50),     # charcoal
    "grayscale(1) brightness(.35)":                         (20, 18, 18, 80),     # black
    "sepia(1) brightness(1.5) saturate(.8)":                (210, 185, 140, 40),  # sand
    "sepia(1) brightness(1.1) saturate(1.6)":               (185, 135, 80, 50),   # camel
    "sepia(1) hue-rotate(-20deg) saturate(2) brightness(.8)":(160, 80, 45, 55),   # rust
    "sepia(1) brightness(.6) saturate(1.2)":                (90, 55, 30, 60),     # brown
    "sepia(1) hue-rotate(30deg) brightness(.7) saturate(1.4)":(85, 95, 40, 55),   # olive
    "hue-rotate(-60deg) saturate(1.5)":                     (140, 30, 100, 55),   # wine
    "hue-rotate(60deg) saturate(1.6) brightness(.9)":       (30, 45, 140, 55),    # navy
    "hue-rotate(150deg) saturate(1.4) brightness(.8)":      (30, 110, 55, 55),    # forest
    "hue-rotate(-30deg) saturate(2)":                       (200, 20, 40, 55),    # crimson
    "hue-rotate(90deg) saturate(1.2) brightness(1.2)":      (110, 185, 230, 45),  # sky
    "hue-rotate(120deg) saturate(1.2)":                     (80, 120, 170, 50),   # steel
    "hue-rotate(170deg) saturate(1.3)":                     (30, 155, 150, 55),   # teal
    "hue-rotate(40deg) saturate(1.1) brightness(1.3)":      (185, 160, 230, 40),  # lavender
    "hue-rotate(200deg) saturate(1.3) brightness(1.1)":     (130, 220, 185, 45),  # mint
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _room_background(w: int, h: int) -> Image.Image:
    """
    Render a high-end dressing room background:
    - warm marble / parquet floor
    - tall, dark panelled walls
    - soft key light from upper-left
    - subtle fill light from right
    - floor reflection strip
    """
    bg = Image.new("RGB", (w, h), (12, 10, 18))
    draw = ImageDraw.Draw(bg)

    # --- wall gradient (dark charcoal with warm tint) ---
    wall_h = int(h * 0.72)
    for y in range(wall_h):
        t = y / wall_h
        r = int(22 + t * 18)
        g = int(18 + t * 12)
        b = int(28 + t * 10)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # --- wall panels (architectural detail) ---
    panel_cols = 3
    pw = w // panel_cols
    for col in range(panel_cols):
        x0 = col * pw + 20
        x1 = x0 + pw - 40
        y0 = 30
        y1 = wall_h - 30
        for line_w, alpha in [(3, 60), (1, 40)]:
            draw.rectangle([x0, y0, x1, y1],
                           outline=(80, 70, 90, alpha), width=line_w)
        # inner bevel
        draw.rectangle([x0 + 10, y0 + 10, x1 - 10, y1 - 10],
                       outline=(55, 48, 65), width=1)

    # --- floor gradient (warm parquet) ---
    for y in range(wall_h, h):
        t = (y - wall_h) / (h - wall_h)
        r = int(45 + t * 20)
        g = int(35 + t * 14)
        b = int(22 + t * 10)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # --- floor wood planks ---
    for i in range(6):
        py = wall_h + i * ((h - wall_h) // 6)
        draw.line([(0, py), (w, py)], fill=(60, 45, 28), width=1)

    # --- key light (soft spotlight from top-centre) ---
    spot = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spot)
    cx, cy = w // 2, 0
    r_light = int(w * 0.55)
    for r in range(r_light, 0, -4):
        alpha = int(38 * (1 - r / r_light) ** 2)
        sd.ellipse([cx - r, cy - r, cx + r, cy + r],
                   fill=(255, 240, 200, alpha))
    bg = Image.alpha_composite(bg.convert("RGBA"), spot).convert("RGB")

    # --- fill light (cold, right side) ---
    fill = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill)
    for r in range(int(w * 0.4), 0, -4):
        alpha = int(14 * (1 - r / (w * 0.4)) ** 2)
        fd.ellipse([w - r, int(h * 0.2) - r, w + r, int(h * 0.2) + r],
                   fill=(180, 200, 255, alpha))
    bg = Image.alpha_composite(bg.convert("RGBA"), fill).convert("RGB")

    # --- floor reflection strip ---
    floor_y = wall_h
    for dy in range(60):
        alpha = int(40 * (1 - dy / 60))
        draw.line([(0, floor_y + dy), (w, floor_y + dy)],
                  fill=(200, 180, 140, alpha))

    return bg


def _body_silhouette(
    w: int, h: int, size_key: str = "M"
) -> Tuple[Image.Image, dict]:
    """
    Draw a smooth, realistic female body silhouette (RGBA).
    Returns (image, geometry_dict) where geometry_dict contains bounding
    boxes for the dress, torso, etc.
    """
    scale = SIZE_SCALES.get(size_key, 1.0)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = w // 2

    # Derived y positions
    head_r = int(w * HEAD_RADIUS_FRAC)
    head_cy = int(h * BODY_TOP_FRAC) + head_r
    neck_y  = head_cy + head_r
    shoulder_y = int(h * SHOULDER_FRAC * 0.55)
    waist_y = int(h * WAIST_FRAC * 0.78)
    hip_y   = int(h * HIP_FRAC * 0.82)
    knee_y  = int(h * 0.74)
    ankle_y = int(h * ANKLE_FRAC * 0.95)

    # Widths (half-widths)
    shoulder_hw = int(w * 0.175 * scale)
    bust_hw      = int(w * 0.155 * scale)
    waist_hw     = int(w * 0.115 * scale)
    hip_hw       = int(w * 0.165 * scale)
    thigh_hw     = int(w * 0.095 * scale)
    knee_hw      = int(w * 0.075 * scale)
    ankle_hw     = int(w * 0.040 * scale)

    skin = (210, 175, 145)       # warm medium skin tone
    skin_dark = (170, 130, 105)  # shadow
    skin_light = (235, 205, 180) # highlight

    # ---- head ----
    draw.ellipse(
        [cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r],
        fill=skin
    )
    # Face highlight
    draw.ellipse(
        [cx - head_r + 6, head_cy - head_r + 4,
         cx + head_r - 16, head_cy + 2],
        fill=skin_light
    )

    # ---- neck ----
    neck_hw = int(head_r * 0.42)
    draw.polygon([
        (cx - neck_hw, neck_y),
        (cx + neck_hw, neck_y),
        (cx + int(neck_hw * 0.8), shoulder_y),
        (cx - int(neck_hw * 0.8), shoulder_y),
    ], fill=skin)

    def body_poly(
        y_top, hw_top, y_bot, hw_bot, tuck=0.0
    ):
        """Helper: draw a trapezoid body segment with a waist tuck."""
        pts = [
            (cx - hw_top, y_top),
            (cx + hw_top, y_top),
            (cx + hw_bot, y_bot),
            (cx - hw_bot, y_bot),
        ]
        return pts

    # ---- torso ----
    torso_pts = [
        (cx - shoulder_hw, shoulder_y),
        (cx + shoulder_hw, shoulder_y),
        (cx + waist_hw,    waist_y),
        (cx - waist_hw,    waist_y),
    ]
    draw.polygon(torso_pts, fill=skin)
    # torso highlight
    hi_pts = [
        (cx - int(shoulder_hw * 0.3), shoulder_y),
        (cx + int(shoulder_hw * 0.3), shoulder_y),
        (cx + int(waist_hw * 0.3),    waist_y),
        (cx - int(waist_hw * 0.3),    waist_y),
    ]
    draw.polygon(hi_pts, fill=skin_light)

    # ---- arms (simple ellipses angled outward) ----
    arm_w = int(w * 0.048 * scale)
    arm_h = int((waist_y - shoulder_y) * 1.12)
    for side in (-1, 1):
        ax = cx + side * int(shoulder_hw * 1.06)
        ay = shoulder_y + int(arm_h * 0.45)
        draw.ellipse(
            [ax - arm_w, ay - arm_h // 2, ax + arm_w, ay + arm_h // 2],
            fill=skin
        )

    # ---- hips ----
    hip_pts = [
        (cx - waist_hw, waist_y),
        (cx + waist_hw, waist_y),
        (cx + hip_hw,   hip_y),
        (cx - hip_hw,   hip_y),
    ]
    draw.polygon(hip_pts, fill=skin)

    # ---- legs ----
    for side in (-1, 1):
        lx = cx + side * int(hip_hw * 0.55)
        # thigh
        draw.polygon([
            (lx - thigh_hw, hip_y),
            (lx + thigh_hw, hip_y),
            (lx + knee_hw,  knee_y),
            (lx - knee_hw,  knee_y),
        ], fill=skin)
        # shin
        draw.polygon([
            (lx - knee_hw,  knee_y),
            (lx + knee_hw,  knee_y),
            (lx + ankle_hw, ankle_y),
            (lx - ankle_hw, ankle_y),
        ], fill=skin)

    # ---- subtle body shading ----
    shading = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shading)
    for side, xs in ((-1, cx - shoulder_hw), (1, cx + shoulder_hw - 30)):
        sd.rectangle([xs, shoulder_y, xs + 30, ankle_y],
                     fill=(0, 0, 0, 18))
    img = Image.alpha_composite(img, shading)

    geom = dict(
        cx=cx,
        dress_x=cx - shoulder_hw,
        dress_y=shoulder_y,
        dress_w=shoulder_hw * 2,
        dress_h=int(ankle_y - shoulder_y),
        waist_y=waist_y,
        hip_y=hip_y,
        shoulder_hw=shoulder_hw,
        hip_hw=hip_hw,
    )
    return img, geom


def _apply_dress(
    body: Image.Image,
    dress_img: Image.Image,
    geom: dict,
    fabric: str,
    colour_filter: str,
) -> Image.Image:
    """
    Composite the dress over the body using the geometry, apply fabric
    texture tinting and colour overlay.
    """
    dx = geom["dress_x"]
    dy = geom["dress_y"]
    dw = geom["dress_w"]
    dh = geom["dress_h"]

    # --- resize dress to fit the body ---
    dress = dress_img.convert("RGBA").resize(
        (dw, dh), Image.LANCZOS
    )

    # --- fabric brightness / contrast ---
    fab = FABRIC_FILTERS.get(fabric, (1.0, 1.0, 1.0, 1.0))
    r_f, g_f, b_f, br = fab
    r, g, b, a = dress.split()
    r = r.point(lambda v: min(255, int(v * r_f * br)))
    g = g.point(lambda v: min(255, int(v * g_f * br)))
    b = b.point(lambda v: min(255, int(v * b_f * br)))
    dress = Image.merge("RGBA", (r, g, b, a))

    # --- colour tint overlay ---
    tint = COLOUR_TINTS.get(colour_filter)
    if tint and tint[3] > 0:
        tr, tg, tb, ta = tint
        tint_layer = Image.new("RGBA", dress.size, (tr, tg, tb, ta))
        dress = Image.alpha_composite(dress, tint_layer)

    # --- subtle dress shadow on body ---
    shadow = Image.new("RGBA", body.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle(
        [dx + 6, dy + 6, dx + dw + 6, dy + dh + 6],
        fill=(0, 0, 0, 40)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    result = Image.alpha_composite(body, shadow)
    result.paste(dress, (dx, dy), dress)
    return result


def _add_room_effects(img: Image.Image, w: int, h: int) -> Image.Image:
    """Add vignette, subtle grain and mirror floor reflection."""
    # vignette
    vig = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    for r in range(max(w, h), 0, -4):
        alpha = int(130 * (r / max(w, h)) ** 3)
        vd.ellipse(
            [w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r],
            outline=(0, 0, 0, alpha), width=4
        )
    img = Image.alpha_composite(img.convert("RGBA"), vig).convert("RGB")

    # floor reflection (bottom 8%)
    refl_h = int(h * 0.08)
    floor_strip = img.crop((0, h - refl_h * 2, w, h - refl_h))
    floor_strip = floor_strip.transpose(Image.FLIP_TOP_BOTTOM)
    floor_strip = ImageEnhance.Brightness(floor_strip).enhance(0.35)
    floor_strip = floor_strip.filter(ImageFilter.GaussianBlur(3))
    img.paste(floor_strip, (0, h - refl_h))

    return img


def _watermark(img: Image.Image, w: int, h: int) -> Image.Image:
    """Add a subtle OMAFRANS COUTURE watermark."""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    text = "OMAFRANS COUTURE"
    # Use default font — works on all systems
    draw.text(
        (w // 2 - len(text) * 4, h - 28),
        text,
        fill=(255, 255, 255, 35),
        align="center"
    )
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


# ---------------------------------------------------------------------------
# Public API & AI Generation (Pollinations.ai Flux & Gemini fallback)
# ---------------------------------------------------------------------------

COLOUR_DESCRIPTIONS: dict[str, str] = {
    "none": "original garment colors",
    "grayscale(1) brightness(1.9)": "ivory white",
    "grayscale(1) brightness(1.2)": "stone gray",
    "grayscale(1) brightness(.7)": "charcoal gray",
    "grayscale(1) brightness(.35)": "midnight black",
    "sepia(1) brightness(1.5) saturate(.8)": "warm sand beige",
    "sepia(1) brightness(1.1) saturate(1.6)": "camel tan",
    "sepia(1) hue-rotate(-20deg) saturate(2) brightness(.8)": "rust terracotta",
    "sepia(1) brightness(.6) saturate(1.2)": "rich chocolate brown",
    "sepia(1) hue-rotate(30deg) brightness(.7) saturate(1.4)": "olive green",
    "hue-rotate(-60deg) saturate(1.5)": "deep wine burgundy",
    "hue-rotate(60deg) saturate(1.6) brightness(.9)": "regal navy blue",
    "hue-rotate(150deg) saturate(1.4) brightness(.8)": "emerald forest green",
    "hue-rotate(-30deg) saturate(2)": "crimson red",
    "hue-rotate(90deg) saturate(1.2) brightness(1.2)": "sky blue",
    "hue-rotate(120deg) saturate(1.2)": "steel blue",
    "hue-rotate(170deg) saturate(1.3)": "deep teal",
    "hue-rotate(40deg) saturate(1.1) brightness(1.3)": "lavender lilac",
    "hue-rotate(200deg) saturate(1.3) brightness(1.1)": "mint green",
}


def _detect_garment_colors(dress_bytes: bytes) -> tuple[str, str]:
    """
    Detect approximate garment silhouette and dominant color from uploaded image bytes.
    """
    try:
        with Image.open(io.BytesIO(dress_bytes)) as img:
            img = img.convert("RGBA")
            w, h = img.size
            ratio = h / max(1, w)
            if ratio > 1.6:
                silhouette = "flowing full-length couture dress or long trench coat"
            elif ratio > 1.1:
                silhouette = "tailored couture midi dress or stylish coat and trousers"
            else:
                silhouette = "bespoke couture outfit"

            # Sample non-transparent pixels to find dominant color
            small = img.resize((32, 32), Image.Resampling.BOX)
            pixels = []
            for r, g, b, a in small.getdata():
                if a > 60:
                    brightness = (r + g + b) / 3
                    if 20 < brightness < 245:
                        pixels.append((r, g, b))

            if pixels:
                avg_r = sum(p[0] for p in pixels) // len(pixels)
                avg_g = sum(p[1] for p in pixels) // len(pixels)
                avg_b = sum(p[2] for p in pixels) // len(pixels)

                diff = max(avg_r, avg_g, avg_b) - min(avg_r, avg_g, avg_b)
                if diff < 22:
                    if max(avg_r, avg_g, avg_b) > 190:
                        color = "elegant ivory cream"
                    elif max(avg_r, avg_g, avg_b) > 110:
                        color = "sophisticated stone gray"
                    else:
                        color = "sleek midnight black"
                elif avg_r > avg_g and avg_b > avg_g:
                    color = "deep regal purple and violet"
                elif avg_r > avg_g and avg_r > avg_b:
                    if avg_g > 110:
                        color = "warm terracotta and camel"
                    else:
                        color = "rich crimson and wine red"
                elif avg_b > avg_r and avg_b > avg_g:
                    color = "regal navy blue"
                elif avg_g > avg_r and avg_g > avg_b:
                    color = "emerald forest green"
                else:
                    color = "signature couture tones"
            else:
                color = "signature couture tones"
            return silhouette, color
    except Exception as exc:
        logger.debug("Garment detection fallback: %s", exc)
        return "bespoke couture outfit", "signature couture tones"


def _generate_with_pollinations(
    dress_bytes: bytes,
    size: str,
    fabric: str,
    colour_filter: str,
    notes: str,
) -> bytes:
    """
    Generate a photorealistic, human-worn fashion photograph using Pollinations.ai (Flux).
    """
    api_key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    if not api_key:
        raise ImageGenerationError(
            "Pollinations is not configured. Set POLLINATIONS_API_KEY in .env and restart the server."
        )

    silhouette, detected_color = _detect_garment_colors(dress_bytes)
    chosen_color = COLOUR_DESCRIPTIONS.get(colour_filter, detected_color)
    if colour_filter == "none":
        chosen_color = detected_color

    prompt_parts = [
        "Photorealistic 8k luxury fashion editorial photograph for Omafrans Couture.",
        "A single elegant adult female fashion model standing gracefully alone,",
        "full body portrait from head to toe, showing natural realistic face looking towards the camera,",
        "natural skin texture, realistic hands, styled hair, graceful posture.",
        f"She is wearing a bespoke {chosen_color} {silhouette} made of {fabric}.",
        f"Tailored to fit size {size} with realistic fabric drape, tailored folds, and luxury couture stitching.",
    ]
    if notes:
        prompt_parts.append(f"Custom design notes: {notes}.")
    prompt_parts.append(
        "Setting: high-end haute couture fitting salon with warm architectural wood panelling and soft studio key lighting,"
        "Vogue editorial fashion photography, 8k, sharp focus, hyperrealistic, authentic human model in real life."
    )
    full_prompt = " ".join(prompt_parts)
    encoded = urllib.parse.quote(full_prompt)

    seed = random.randint(1000, 999999)
    endpoints = [
        f"https://gen.pollinations.ai/image/{encoded}?model=flux&width=768&height=1024&nologo=true&seed={seed}&key={api_key}",
        f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width=768&height=1024&nologo=true&seed={seed}&key={api_key}",
    ]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "OmafransCouture/1.0",
    }

    last_error = None
    for url in endpoints:
        try:
            resp = requests.get(url, headers=headers, timeout=75)
            if resp.status_code == 200 and resp.content and resp.content.startswith((b"\xff\xd8", b"\x89PNG", b"RIFF")):
                with Image.open(io.BytesIO(resp.content)) as im:
                    im.load()
                    out = io.BytesIO()
                    im.convert("RGB").save(out, format="PNG")
                    logger.info("Successfully generated fitting image with Pollinations Flux.")
                    return out.getvalue()
            elif resp.status_code in (401, 403):
                raise ImageGenerationError("Pollinations rejected the API key. Check POLLINATIONS_API_KEY in .env.")
            elif resp.status_code == 429:
                raise ImageGenerationError("Pollinations rate limit reached. Please wait a moment and try again.")
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
        except requests.Timeout as exc:
            last_error = "Pollinations request timed out."
            logger.warning("Pollinations timeout for %s: %s", url, exc)
        except requests.RequestException as exc:
            last_error = str(exc)
            logger.warning("Pollinations request failed for %s: %s", url, exc)

    raise ImageGenerationError(f"Pollinations generation failed: {last_error or 'No response'}")


def _generate_with_gemini(
    dress_bytes: bytes,
    size: str,
    fabric: str,
    colour_filter: str,
    notes: str,
) -> bytes | None:
    """
    Generate a photorealistic fitting preview with Gemini.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ImageGenerationError(
            "Gemini is not configured. Set GEMINI_API_KEY in .env."
        )

    b64_dress = base64.b64encode(dress_bytes).decode("ascii")
    mime = "image/png"
    if dress_bytes.startswith(b"\xff\xd8"):
        mime = "image/jpeg"
    elif dress_bytes.startswith(b"RIFF") and dress_bytes[8:12] == b"WEBP":
        mime = "image/webp"

    prompt = (
        "Create one photorealistic, full-length luxury fashion photograph for "
        "Omafrans Couture. Show a real adult woman wearing that exact garment naturally on her "
        "body. Recreate the garment faithfully: preserve its colour, "
        "cut, silhouette, fabric appearance, pattern, and visible details. "
        "Show one person from head to toe, with a visible natural face and realistic human anatomy, "
        "hands, proportions, skin, and fabric folds. The person must be the "
        "main subject and the garment must be clearly visible. Compose a "
        "single vertical 3:4 editorial photograph in a refined couture fitting "
        "room with soft, realistic studio lighting. "
        f"Selected size: {size}. Fabric preference: {fabric}. "
        f"{f'User design notes: {notes}. ' if notes else ''}"
    )

    model = "gemini-3.1-flash-image"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": mime,
                            "data": b64_dress,
                        }
                    },
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": "3:4"},
        },
    }
    resp = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=100,
    )
    if resp.status_code == 200:
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    image_bytes = base64.b64decode(inline["data"], validate=True)
                    with Image.open(io.BytesIO(image_bytes)) as image:
                        image.load()
                        output = io.BytesIO()
                        image.convert("RGB").save(output, format="PNG")
                    return output.getvalue()
    raise ImageGenerationError(f"Gemini generation returned status {resp.status_code}")


def generate_try_on(
    dress_bytes: bytes,
    size: str = "M",
    fabric: str = "Premium Gabardine",
    colour_filter: str = "none",
    notes: str = "",
) -> tuple[bytes, bool]:
    """
    Generate a photorealistic dressing-room try-on image with Pollinations.ai (Flux)
    or Gemini as fallback.

    :param dress_bytes:   Raw bytes of the uploaded dress image.
    :param size:          One of XS / S / M / L / XL / 2XL.
    :param fabric:        Fabric name matching FABRIC_FILTERS keys.
    :param colour_filter: CSS filter string matching COLOUR_TINTS keys.
    :param notes:         Free-text design notes.
    :returns:             (PNG bytes, True)
    """
    # 1. Primary: Pollinations.ai Flux
    if os.environ.get("POLLINATIONS_API_KEY", "").strip():
        try:
            generated_image = _generate_with_pollinations(
                dress_bytes, size, fabric, colour_filter, notes
            )
            return generated_image, True
        except ImageGenerationError as exc:
            logger.warning("Pollinations failed: %s", exc)
            if not os.environ.get("GEMINI_API_KEY", "").strip():
                raise

    # 2. Secondary fallback: Gemini
    if os.environ.get("GEMINI_API_KEY", "").strip():
        generated_image = _generate_with_gemini(
            dress_bytes, size, fabric, colour_filter, notes
        )
        return generated_image, True

    raise ImageGenerationError(
        "No AI generation key configured. Please set POLLINATIONS_API_KEY in .env."
    )

