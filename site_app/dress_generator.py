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
import socket
import time
from typing import Tuple
import urllib.parse

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, UnidentifiedImageError

logger = logging.getLogger(__name__)

# Ensure resilient DNS resolution for Pollinations on all operating systems.
# NOTE: requests/urllib3 imports socket at their own import time, so we must
# patch both the stdlib socket module AND urllib3's internal socket reference
# to guarantee the override takes effect regardless of import order.
_SYSTEM_GETADDRINFO = socket.getaddrinfo

POLLINATIONS_FALLBACK_IPS = ("104.18.6.216", "104.18.7.216")


def _resilient_getaddrinfo(host, port, *args, **kwargs):
    try:
        return _SYSTEM_GETADDRINFO(host, port, *args, **kwargs)
    except socket.gaierror:
        if "pollinations.ai" in str(host):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))
                for ip in POLLINATIONS_FALLBACK_IPS
            ]
        raise


socket.getaddrinfo = _resilient_getaddrinfo

# Also patch urllib3's connection module which may have cached the original
# socket.getaddrinfo reference before this module was imported.
try:
    import urllib3.util.connection as _urllib3_conn
    _urllib3_conn.socket.getaddrinfo = _resilient_getaddrinfo  # type: ignore[attr-defined]
except Exception:
    pass


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
    "XS":  0.82,
    "S":   0.91,
    "M":   1.00,
    "L":   1.09,
    "XL":  1.18,
    "2XL": 1.30,
    "3XL": 1.44,
    "4XL": 1.58,
    "5XL": 1.72,
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
    Render a bright, airy dressing room background:
    - light warm cream/beige walls
    - soft parquet floor
    - gentle spotlight from above
    """
    bg = Image.new("RGB", (w, h), (240, 232, 220))
    draw = ImageDraw.Draw(bg)

    wall_h = int(h * 0.72)

    # Light warm wall gradient
    for y in range(wall_h):
        t = y / wall_h
        r = int(238 - t * 12)
        g = int(228 - t * 10)
        b = int(215 - t * 8)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Subtle wall panels
    panel_cols = 3
    pw = w // panel_cols
    for col in range(panel_cols):
        x0 = col * pw + 20
        x1 = x0 + pw - 40
        y0 = 30
        y1 = wall_h - 30
        draw.rectangle([x0, y0, x1, y1], outline=(200, 190, 178), width=2)
        draw.rectangle([x0 + 10, y0 + 10, x1 - 10, y1 - 10], outline=(210, 200, 188), width=1)

    # Warm parquet floor
    for y in range(wall_h, h):
        t = (y - wall_h) / (h - wall_h)
        r = int(195 + t * 15)
        g = int(168 + t * 10)
        b = int(125 + t * 8)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Floor planks
    for i in range(8):
        py = wall_h + i * ((h - wall_h) // 8)
        draw.line([(0, py), (w, py)], fill=(170, 145, 105), width=1)

    # Soft key spotlight from above
    spot = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spot)
    cx, cy = w // 2, 0
    r_light = int(w * 0.6)
    for r in range(r_light, 0, -4):
        alpha = int(28 * (1 - r / r_light) ** 2)
        sd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 248, 230, alpha))
    bg = Image.alpha_composite(bg.convert("RGBA"), spot).convert("RGB")

    # Floor highlight strip at wall/floor join
    for dy in range(30):
        alpha = int(20 * (1 - dy / 30))
        draw.line([(0, wall_h + dy), (w, wall_h + dy)], fill=(255, 240, 200, alpha))

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
    skin_dark = (160, 122, 96)   # shadow side
    skin_light = (240, 214, 188) # highlight side
    hair = (45, 34, 28)          # dark brown hair

    # ------------------------------------------------------------------
    # Shading layer (gives the flat polygons 3D volume)
    # ------------------------------------------------------------------
    shade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)

    # ------------------------------------------------------------------
    # Head / face
    # ------------------------------------------------------------------
    draw.ellipse(
        [cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r],
        fill=skin,
    )
    # Face highlight (light from upper-left)
    draw.ellipse(
        [cx - head_r + 6, head_cy - head_r + 5,
         cx + head_r - 16, head_cy + 4],
        fill=skin_light,
    )
    # Shadow on right side of face
    sd.ellipse(
        [cx + head_r - 14, head_cy - 10, cx + head_r + 4, head_cy + head_r - 6],
        fill=(0, 0, 0, 30),
    )
    # Subtle facial features
    eye_y = head_cy - int(head_r * 0.18)
    draw.ellipse([cx - head_r + 14, eye_y - 3, cx - head_r + 22, eye_y + 3], fill=(60, 50, 45))
    draw.ellipse([cx + head_r - 22, eye_y - 3, cx + head_r - 14, eye_y + 3], fill=(60, 50, 45))
    draw.ellipse([cx - 2, head_cy + 4, cx + 2, head_cy + 8], fill=(150, 90, 70))

    # Hair cap framing the face
    draw.pieslice(
        [cx - head_r - 4, head_cy - head_r - 6, cx + head_r + 4, head_cy + head_r + 2],
        180, 360, fill=hair,
    )
    draw.rectangle([cx - head_r - 4, head_cy - 6, cx + head_r + 4, head_cy + head_r], fill=hair)

    # ------------------------------------------------------------------
    # Neck
    # ------------------------------------------------------------------
    neck_hw = int(head_r * 0.42)
    draw.polygon([
        (cx - neck_hw, neck_y),
        (cx + neck_hw, neck_y),
        (cx + int(neck_hw * 0.85), shoulder_y),
        (cx - int(neck_hw * 0.85), shoulder_y),
    ], fill=skin)
    sd.rectangle([cx + int(neck_hw * 0.5), neck_y, cx + neck_hw, shoulder_y], fill=(0, 0, 0, 22))

    # ------------------------------------------------------------------
    # Torso (bust -> waist -> hips hourglass)
    # ------------------------------------------------------------------
    draw.polygon([
        (cx - shoulder_hw, shoulder_y),
        (cx + shoulder_hw, shoulder_y),
        (cx + bust_hw, int((shoulder_y + waist_y) / 2)),
        (cx - bust_hw, int((shoulder_y + waist_y) / 2)),
    ], fill=skin)
    draw.polygon([
        (cx - bust_hw, int((shoulder_y + waist_y) / 2)),
        (cx + bust_hw, int((shoulder_y + waist_y) / 2)),
        (cx + waist_hw, waist_y),
        (cx - waist_hw, waist_y),
    ], fill=skin)
    draw.polygon([
        (cx - waist_hw, waist_y),
        (cx + waist_hw, waist_y),
        (cx + hip_hw, hip_y),
        (cx - hip_hw, hip_y),
    ], fill=skin)
    # Torso shading (right side darker = volume)
    sd.polygon([
        (cx + bust_hw * 0.55, shoulder_y),
        (cx + shoulder_hw, shoulder_y),
        (cx + shoulder_hw, int((shoulder_y + waist_y) / 2)),
        (cx + bust_hw * 0.65, int((shoulder_y + waist_y) / 2)),
    ], fill=(0, 0, 0, 20))
    sd.polygon([
        (cx + waist_hw * 0.65, int((shoulder_y + waist_y) / 2)),
        (cx + bust_hw * 0.65, int((shoulder_y + waist_y) / 2)),
        (cx + hip_hw * 0.65, hip_y),
        (cx + waist_hw * 0.75, hip_y),
    ], fill=(0, 0, 0, 24))

    # ------------------------------------------------------------------
    # Arms (upper + forearm, slightly bent)
    # ------------------------------------------------------------------
    arm_w = int(w * 0.045 * scale)
    arm_len = int((waist_y - shoulder_y) * 1.05)
    for side in (-1, 1):
        ax = cx + side * int(shoulder_hw * 1.02)
        ay = shoulder_y + int(arm_len * 0.5)
        draw.ellipse([ax - arm_w, ay - int(arm_len * 0.5),
                      ax + arm_w, ay + int(arm_len * 0.5)], fill=skin)
        bx = cx + side * int(shoulder_hw * 1.45)
        by = waist_y + int(arm_len * 0.15)
        draw.ellipse([bx - int(arm_w * 0.85), by - int(arm_len * 0.35),
                      bx + int(arm_w * 0.85), by + int(arm_len * 0.35)], fill=skin)
        sd.ellipse([ax + side * int(arm_w * 0.4), ay - int(arm_len * 0.45),
                    ax + side * int(arm_w * 1.1), ay + int(arm_len * 0.45)],
                   fill=(0, 0, 0, 18))

    # ------------------------------------------------------------------
    # Legs (thigh + shin) + feet
    # ------------------------------------------------------------------
    for side in (-1, 1):
        lx = cx + side * int(hip_hw * 0.52)
        draw.polygon([(lx - thigh_hw, hip_y),
                      (lx + thigh_hw, hip_y),
                      (lx + knee_hw, knee_y),
                      (lx - knee_hw, knee_y)], fill=skin)
        draw.polygon([(lx - knee_hw, knee_y),
                      (lx + knee_hw, knee_y),
                      (lx + ankle_hw, ankle_y),
                      (lx - ankle_hw, ankle_y)], fill=skin)
        sx = lx + side * int(thigh_hw * 0.5)
        sd.polygon([(sx, hip_y), (sx + int(thigh_hw * 0.6), hip_y),
                    (sx + int(knee_hw * 0.6), knee_y), (sx, knee_y)], fill=(0, 0, 0, 18))
        foot_w = int(w * 0.035 * scale)
        fx = cx + side * int(hip_hw * 0.5)
        draw.ellipse([fx - foot_w, ankle_y - int(foot_w * 0.6),
                      fx + foot_w, ankle_y + int(foot_w * 0.6)], fill=skin_dark)

    # Apply shading for 3D volume
    img = Image.alpha_composite(img, shade)

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
    Composite the *actual uploaded dress* onto the body figure.

    The dress is scaled to the shoulder width while preserving its aspect
    ratio, so the print, colours and cut of the uploaded garment are kept
    exactly — nothing is invented by an AI generator. A subtle contour
    shading is laid over the fabric so it looks like it sits on a curved
    body rather than floating as a flat rectangle.
    """
    dx = geom["dress_x"]
    dy = geom["dress_y"]
    dw = geom["dress_w"]

    dress = dress_img.convert("RGBA")
    dw_px = max(1, int(dw))
    # Preserve aspect ratio: scale to shoulder width, height follows so the
    # print is never stretched or squashed.
    scale = dw_px / dress.width
    new_h = max(1, int(dress.height * scale))
    dress = dress.resize((dw_px, new_h), Image.LANCZOS)

    # --- fabric brightness / contrast (kept subtle so colours stay exact) ---
    fab = FABRIC_FILTERS.get(fabric, (1.0, 1.0, 1.0, 1.0))
    r_f, g_f, b_f, br = fab
    r, g, b, a = dress.split()
    r = r.point(lambda v: min(255, int(v * r_f * br)))
    g = g.point(lambda v: min(255, int(v * g_f * br)))
    b = b.point(lambda v: min(255, int(v * b_f * br)))
    dress = Image.merge("RGBA", (r, g, b, a))

    # --- colour tint overlay (light, preserves underlying print) ---
    tint = COLOUR_TINTS.get(colour_filter)
    if tint and tint[3] > 0:
        tr, tg, tb, ta = tint
        ta = max(0, int(ta * 0.5))  # half-strength so the print still shows
        tint_layer = Image.new("RGBA", dress.size, (tr, tg, tb, ta))
        dress = Image.alpha_composite(dress, tint_layer)

    # --- body-contour shading: darker at sides, brighter down the centre ---
    dw_, dh_ = dress.size
    shade = Image.new("RGBA", (dw_, dh_), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for x in range(dw_):
        t = abs(x - dw_ // 2) / max(1, dw_ // 2)  # 0 at centre, 1 at edge
        alpha = int(45 * t * t)  # stronger at edges = curved-body shading
        sd.line([(x, 0), (x, dh_)], fill=(0, 0, 0, alpha))
    dress = Image.alpha_composite(dress, shade)

    # --- paste onto body at shoulder line, centred horizontally ---
    px = dx + (int(dw) - dw_) // 2
    result = body.convert("RGBA")
    result.paste(dress, (px, dy), dress)
    return result


def _add_room_effects(img: Image.Image, w: int, h: int) -> Image.Image:
    """Add very light vignette and subtle floor reflection."""
    # Gentle vignette — much lighter than before
    vig = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    for r in range(max(w, h), 0, -6):
        alpha = int(55 * (r / max(w, h)) ** 4)
        vd.ellipse(
            [w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r],
            outline=(0, 0, 0, alpha), width=6
        )
    img = Image.alpha_composite(img.convert("RGBA"), vig).convert("RGB")

    # Subtle floor reflection (bottom 6%)
    refl_h = int(h * 0.06)
    floor_strip = img.crop((0, h - refl_h * 2, w, h - refl_h))
    floor_strip = floor_strip.transpose(Image.FLIP_TOP_BOTTOM)
    floor_strip = ImageEnhance.Brightness(floor_strip).enhance(0.45)
    floor_strip = floor_strip.filter(ImageFilter.GaussianBlur(2))
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
# Public API & AI Generation (Gemini reference-image try-on, Pollinations fallback)
# ---------------------------------------------------------------------------

COLOUR_DESCRIPTIONS: dict[str, str] = {
    "none": "original garment colors",
    "grayscale(1) brightness(1.9)": "ivory cream white",
    "grayscale(1) brightness(1.2)": "sophisticated stone gray",
    "grayscale(1) brightness(.7)": "refined charcoal gray",
    "grayscale(1) brightness(.35)": "sleek midnight onyx black",
    "sepia(1) brightness(1.5) saturate(.8)": "warm desert sand beige",
    "sepia(1) brightness(1.1) saturate(1.6)": "luxury camel tan",
    "sepia(1) hue-rotate(-20deg) saturate(2) brightness(.8)": "rust terracotta",
    "sepia(1) brightness(.6) saturate(1.2)": "rich chocolate brown",
    "sepia(1) hue-rotate(30deg) brightness(.7) saturate(1.4)": "tailored olive green",
    "hue-rotate(-60deg) saturate(1.5)": "deep royal wine burgundy",
    "hue-rotate(-60deg) saturate(1.8) brightness(.9)": "regal plum violet",
    "hue-rotate(60deg) saturate(1.6) brightness(.9)": "regal navy blue",
    "hue-rotate(150deg) saturate(1.4) brightness(.8)": "emerald forest green",
    "hue-rotate(-30deg) saturate(2)": "vibrant crimson red",
    "hue-rotate(90deg) saturate(1.2) brightness(1.2)": "sky blue",
    "hue-rotate(120deg) saturate(1.2)": "steel blue",
    "hue-rotate(170deg) saturate(1.3)": "deep couture teal",
    "hue-rotate(40deg) saturate(1.1) brightness(1.3)": "lavender lilac",
    "hue-rotate(200deg) saturate(1.3) brightness(1.1)": "mint green",
}

SIZE_PROPORTIONS: dict[str, str] = {
    "XS": "petite slender XS frame, Bust 80cm Waist 62cm Hips 86cm, very narrow waist and slim fit",
    "S":  "lean toned S frame, Bust 85cm Waist 67cm Hips 91cm, slender athletic build",
    "M":  "classic M frame, Bust 90cm Waist 72cm Hips 96cm, balanced natural feminine curves",
    "L":  "curvaceous L frame, Bust 96cm Waist 78cm Hips 102cm, fuller bust prominent feminine hips",
    "XL": "full-figured XL frame, Bust 103cm Waist 85cm Hips 109cm, voluptuous curves generous hips",
    "2XL":"plus-size 2XL frame, Bust 111cm Waist 93cm Hips 117cm, richly curvy full-figured body",
    "3XL":"chubby 3XL plus-size frame, Bust 120cm Waist 102cm Hips 126cm, chubby rounder belly soft arms and thighs",
    "4XL":"very fat 4XL plus-size frame, Bust 130cm Waist 112cm Hips 136cm, a very full figure with a round belly, full arms and thighs",
    "5XL":"very fat 5XL plus-size frame, Bust 142cm Waist 124cm Hips 148cm, an extremely full figure with a large round belly, very full arms and thighs, and wide hips",
}

VIEW_DESCRIPTIONS: dict[str, str] = {
    "front": "front view, facing the camera",
    "left": "left-side three-quarter view, turned to the model's left so the garment's left side is visible",
    "back": "rear view, facing away from the camera so the back of the garment is clearly visible",
    "right": "right-side three-quarter view, turned to the model's right so the garment's right side is visible",
}


def _analyze_garment_vision(dress_bytes: bytes, api_key: str, notes: str = "") -> str:
    """
    Use multimodal vision to inspect the uploaded cloth and extract exact couture details.
    Captures exact textile type (e.g. African wax print / Ankara, lace, silk), exact construction
    (e.g. two-piece peplum top with matching pencil skirt, gown), exact primary and contrast colors,
    and all distinctive tailoring details (collar, borders, sleeves, waist flounces, bow/knot).
    """
    if not api_key:
        return ""
    try:
        # Preserve small print and trim details for the visual analysis request.
        with Image.open(io.BytesIO(dress_bytes)) as im:
            im = im.convert("RGB")
            im.thumbnail((768, 768), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=88)
            b64_img = base64.b64encode(buf.getvalue()).decode("ascii")

        if notes:
            prompt = (
                f"A fashion client uploaded this garment image as reference and specified these custom modifications: '{notes}'. "
                "Inspect the uploaded clothing item on the mannequin or display. "
                "Identify its textile type (e.g. African wax print / Ankara, lace, silk, velvet), construction (e.g. two-piece peplum top with pencil skirt, dress), "
                "exact colors, patterns, and tailoring details. "
                f"Describe the customized couture outfit in 4 concise sentences for an AI image generator to dress a real living female model. "
                f"The outfit must strictly follow the client's custom design requirements ('{notes}') as the primary design, "
                "while drawing authentic craftsmanship, fabric patterns, and tailoring details from the reference garment."
            )
        else:
            prompt = (
                "You are an expert couture fashion stylist inspecting an uploaded garment on a dressmaker display or mannequin. "
                "Analyze and state: "
                "1. Cultural and textile style: state whether it is African wax print / Ankara fabric, lace, silk, velvet, brocade, etc. "
                "2. Precise garment construction: two-piece peplum blouse with matching pencil skirt, evening dress, jumpsuit, etc. "
                "3. Exact colors and trims: primary colors (e.g. royal blue) and contrast borders/piping (e.g. bright canary yellow). "
                "4. Distinctive tailoring details: neckline (e.g. V-neck with contrast borders), waist (e.g. tiered peplum flounce hem, front bow knot), sleeves (e.g. puffed sleeves with cuffs), and skirt silhouette. "
                "Describe all clearly visible garment details in 4 concise sentences. Do not invent details that cannot be seen."
            )

        resp = requests.post(
            "https://gen.pollinations.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-5.4-nano",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
                            },
                        ],
                    }
                ],
                "max_tokens": 320,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                desc = choices[0].get("message", {}).get("content", "").strip()
                if desc and len(desc) > 20:
                    logger.info("Vision analyzed uploaded cloth: %s", desc[:100])
                    return desc
        logger.warning("Vision analysis returned status %s: %s", resp.status_code, resp.text[:120])
    except Exception as exc:
        logger.warning("Vision analysis exception: %s", exc)

    return ""


def _detect_garment_colors(dress_bytes: bytes) -> tuple[str, str]:
    """
    Detect approximate garment silhouette and dominant color from uploaded image bytes (fallback).
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
    view: str = "front",
) -> bytes:
    """
    Generate a photorealistic fashion photograph using Pollinations.ai (Flux).
    The prompt uses a vision-generated garment description; exact image reproduction
    cannot be guaranteed by a text-to-image provider.
    """
    api_key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    if not api_key:
        raise ImageGenerationError(
            "Pollinations is not configured. Set POLLINATIONS_API_KEY in .env."
        )

    # 1. Deep vision analysis of the uploaded garment
    garment_detail = _analyze_garment_vision(dress_bytes, api_key, notes=notes)

    if not garment_detail:
        if notes:
            garment_detail = f"bespoke couture outfit with these exact details: {notes}"
        else:
            silhouette, detected_color = _detect_garment_colors(dress_bytes)
            garment_detail = f"{detected_color} {silhouette}"

    # Truncate garment detail to avoid URL length limits (Pollinations 404s on URLs > ~2500 chars)
    garment_detail = garment_detail[:400]

    # 2. Body size
    size_key = size.upper()
    body_proportion = SIZE_PROPORTIONS.get(
        size_key,
        f"size {size_key} body proportions"
    )

    # 3. Fabric texture instruction
    fabric_instruction = {
        "Premium Gabardine": "woven gabardine fabric with crisp structured drape and subtle diagonal twill texture",
        "Organic Cotton":    "soft organic cotton fabric with natural matte finish and gentle fabric folds",
        "Premium Satin":     "luxurious satin fabric with smooth high sheen and glossy light reflections",
        "Fine Jersey":       "stretchy fine jersey fabric that clings to body curves with fluid drape",
        "Premium Linen":     "premium linen fabric with natural slub texture and relaxed refined drape",
    }.get(fabric, f"{fabric} fabric texture and finish")

    # 4. Colour override
    chosen_color = COLOUR_DESCRIPTIONS.get(colour_filter, "")
    if colour_filter and colour_filter != "none" and chosen_color:
        color_instruction = (
            f"The garment COLOR must be entirely changed to {chosen_color}. "
            f"Keep every cut, seam, embroidery, pattern print, and structural detail IDENTICAL to the reference — only the color changes to {chosen_color}."
        )
    else:
        color_instruction = (
            "Use the original garment colors and reproduce the visible print, contrast borders, and color blocks as closely as possible."
        )

    # 5. Build the photorealistic prompt
    #    Flux-realism responds best to: camera lens spec, lighting style, skin detail,
    #    pose naturalness, and explicit "photograph" framing — NOT imperative commands.
    if notes:
        design_directive = (
            f"The garment has been customised as follows: {notes}. "
            f"Incorporate every modification while preserving the base construction."
        )
    else:
        design_directive = ""

    view_desc = VIEW_DESCRIPTIONS.get(view, VIEW_DESCRIPTIONS["front"])

    prompt = (
        # Camera / medium — anchors Flux in photographic space
        "RAW photo, 85mm portrait lens, f/2.8 aperture, ISO 400, sharp focus on garment and face, "
        "natural depth of field, true-to-life colours, no digital painting, no illustration. "
        # Subject
        f"Full-body editorial fashion photograph of a real Black African woman, "
        f"age 24, smooth dark skin with natural pores and realistic skin texture, "
        f"high cheekbones, natural almond-shaped eyes, relaxed confident expression, "
        f"styled natural hair, {body_proportion}. "
        # Garment
        f"She is wearing: {garment_detail}. "
        f"{color_instruction} "
        f"Fabric: {fabric_instruction}. "
        f"{design_directive}"
        # Fit and pose
        f"The garment fits her body perfectly — fabric drapes and creases naturally over her curves. "
        f"She is standing in a relaxed model pose, weight shifted slightly to one hip, "
        f"hands loosely at her sides. {view_desc.capitalize()}. "
        f"Entire figure visible from head to toe including feet. "
        # Scene / lighting
        "Setting: upscale Lagos fashion boutique with white plaster walls, "
        "warm herringbone parquet floor, and a large softbox key light from the upper-left "
        "creating soft even illumination with a gentle fill from the right — no harsh shadows, "
        "no blown highlights, well-exposed skin and fabric. "
        # Quality anchors
        "Vogue West Africa editorial quality, photorealistic, sharp fabric texture, "
        "realistic human anatomy, natural hands and fingers, "
        "no mannequin, no flat lay, no CGI render, no cartoon."
    )

    seed_base = abs(hash(f"{size}_{colour_filter}_{fabric}_{notes}_{garment_detail[:30]}")) % 900000 + 10000

    # POST to /generate so the prompt goes in the body (no URL length limit).
    # Use flux-realism model for maximum photographic realism.
    post_url = "https://image.pollinations.ai/generate"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "OmafransCouture/2.0",
        "Connection": "close",  # prevents keep-alive pool from corrupting the POST path
    }

    last_error = None
    for attempt, seed in enumerate((seed_base, seed_base + 1, seed_base + 2)):
        if attempt > 0:
            # Pollinations rate-limits ~1 image per 45 s on standard keys.
            # Wait before retrying to avoid hitting the cooldown 404.
            logger.info("Waiting 50s before retry (Pollinations rate-limit cooldown)...")
            time.sleep(50)
        payload = {
            "prompt": prompt,
            "model": "flux-realism",   # photorealistic model — far more lifelike than base flux
            "width": 768,
            "height": 1024,
            "nologo": True,
            "seed": seed,
            "enhance": False,          # disable: enhance over-stylises and reduces realism
        }
        try:
            # Fresh session every attempt — prevents connection-pool reuse corruption
            # where a prior GET to /prompt/... causes POST to land on /prompt/generate.
            with requests.Session() as sess:
                resp = sess.post(post_url, json=payload, headers=headers, timeout=90)
            if resp.status_code == 200 and resp.content:
                try:
                    with Image.open(io.BytesIO(resp.content)) as im:
                        im.load()
                        image_format = im.format
                        out = io.BytesIO()
                        im.convert("RGB").save(out, format="PNG")
                    logger.info(
                        "Pollinations flux-realism generated image (format=%s, seed=%s).",
                        image_format, seed,
                    )
                    return out.getvalue()
                except (UnidentifiedImageError, OSError):
                    content_type = resp.headers.get("Content-Type", "unknown")
                    last_error = (
                        f"Pollinations returned non-image content "
                        f"(HTTP 200, content-type {content_type})."
                    )
                    logger.warning("%s", last_error)
            elif resp.status_code in (401, 403):
                raise ImageGenerationError("Pollinations rejected the API key. Check POLLINATIONS_API_KEY.")
            elif resp.status_code == 402:
                raise ImageGenerationError(
                    "Pollinations image quota or account limit reached. Check the provider account's usage and billing."
                )
            elif resp.status_code == 429:
                raise ImageGenerationError(
                    "Pollinations rate limit reached. Wait before trying again or use an account with available quota."
                )
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                logger.warning("Pollinations attempt failed (seed %s): %s", seed, last_error)
        except requests.Timeout:
            last_error = "Pollinations request timed out."
            logger.warning("Pollinations timeout for seed %s", seed)
        except requests.RequestException as exc:
            last_error = str(exc)
            logger.warning("Pollinations request error: %s", exc)

    raise ImageGenerationError(f"Pollinations generation failed: {last_error or 'No response'}")


def _generate_with_gemini(
    dress_bytes: bytes,
    size: str,
    fabric: str,
    colour_filter: str,
    notes: str,
    view: str = "front",
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

    garment_intro = (
        "The uploaded image is the garment source of truth. Transfer the SAME physical garment from "
        "that image onto the model; do not redesign, simplify, substitute, or stylize it. Preserve the "
        "exact silhouette, panel layout, neckline, sleeves, peplum, skirt, seams, trim, border placement, "
        "fabric print scale, motifs, colours, lettering, and visible imperfections. The mannequin, studio, "
        "and background in the reference are not part of the outfit."
    )
    if notes:
        garment_intro += (
            f" Apply only these requested alterations, and leave every unmentioned garment detail unchanged: '{notes}'."
        )

    view_direction = VIEW_DESCRIPTIONS.get(view, VIEW_DESCRIPTIONS["front"])
    prompt = (
        "RAW photo, 85mm portrait lens, f/2.8, ISO 400, natural depth of field, true-to-life colours. "
        "Full-body editorial fashion photograph of a real Black African woman, smooth dark skin, "
        "natural hair, relaxed confident model pose, weight shifted to one hip, standing in a bright "
        "upscale boutique fitting room with white walls and warm parquet floor, soft even studio lighting. "
        "This is a reference-image virtual try-on, not a fashion illustration or a new outfit design. "
        f"{garment_intro} "
        "Entire figure visible head to toe. Realistic human anatomy, natural hands and fingers, "
        f"realistic fabric folds and drape. {view_direction.capitalize()}. "
        f"Size: {size}. Fabric: {fabric}. "
        f"Colour: {COLOUR_DESCRIPTIONS.get(colour_filter, 'original garment colours')}. "
        "Apply colour to garment only — do not change skin, hair, or background. "
        f"{f'Client modifications: {notes}.' if notes else ''} "
        "Vogue West Africa editorial quality, photorealistic, no mannequin, no flat lay, no CGI, "
        "no cartoon, no painting, no altered print, no different garment."
    )

    model = "gemini-3.1-flash-image"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
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
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            timeout=100,
        )
    except requests.RequestException as exc:
        raise ImageGenerationError("Gemini request failed due to a network error.") from exc
    if resp.status_code == 200:
        try:
            data = resp.json()
        except ValueError as exc:
            raise ImageGenerationError("Gemini returned an unreadable response.") from exc
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
        raise ImageGenerationError(
            "Gemini returned no generated image. Check the model's image-generation access and account quota."
        )
    if resp.status_code == 429:
        raise ImageGenerationError(
            "Gemini rate limit or image-generation quota reached. Check Gemini API usage and billing, then try again."
        )
    if resp.status_code in (401, 403):
        raise ImageGenerationError(
            "Gemini rejected the API key or image-generation access. Check GEMINI_API_KEY and the project's permissions."
        )
    raise ImageGenerationError(f"Gemini generation failed (HTTP {resp.status_code}).")


def generate_try_on(
    dress_bytes: bytes,
    size: str = "M",
    fabric: str = "Premium Gabardine",
    colour_filter: str = "none",
    notes: str = "",
    view: str = "front",
) -> tuple[bytes, bool]:
    """
    Generate a photorealistic dressing-room try-on image.

    :param dress_bytes:   Raw bytes of the uploaded dress image.
    :param size:          One of XS through 5XL.
    :param fabric:        Fabric name matching FABRIC_FILTERS keys.
    :param colour_filter: CSS filter string matching COLOUR_TINTS keys.
    :param notes:         Free-text design notes.
    :param view:          Requested camera angle: front, left, back, or right.
    :returns:             (PNG bytes, True)
    """
    if view not in VIEW_DESCRIPTIONS:
        raise ImageGenerationError("Invalid model view. Choose front, left, back, or right.")

    pollinations_key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()

    # Gemini receives the garment pixels as part of the generation request.  It must be
    # preferred for try-on: Pollinations only receives a textual garment description and
    # therefore cannot preserve an exact wax print, trim placement, or construction.
    if gemini_key:
        try:
            generated_image = _generate_with_gemini(
                dress_bytes, size, fabric, colour_filter, notes, view
            )
            return generated_image, True
        except ImageGenerationError as exc:
            logger.warning("Gemini reference-image try-on failed: %s", exc)

    # Do not silently replace a failed reference-image request with a generic
    # illustration. If Gemini is configured, surface its actionable error so the
    # user never mistakes a stock fallback image for their fitting result.
    if pollinations_key and not gemini_key:
        try:
            generated_image = _generate_with_pollinations(
                dress_bytes, size, fabric, colour_filter, notes, view
            )
            return generated_image, True
        except ImageGenerationError as exc:
            logger.warning("Pollinations approximate fallback failed: %s", exc)
            raise ImageGenerationError(f"Pollinations approximate preview failed: {exc}") from exc

    if gemini_key:
        raise ImageGenerationError(
            "Gemini could not generate the reference-image fitting preview. "
            "The generic Pollinations fallback was disabled so an unrelated image is not shown."
        )

    raise ImageGenerationError(
        "No AI generation key configured. Set POLLINATIONS_API_KEY or GEMINI_API_KEY."
    )


def _generate_pillow_composite(
    dress_bytes: bytes,
    size: str = "M",
    fabric: str = "Premium Gabardine",
    colour_filter: str = "none",
) -> bytes:
    """
    Pure-Pillow dressing room composite. Zero external dependencies.
    Always works on any server.
    """
    W, H = CANVAS_W, CANVAS_H
    bg = _room_background(W, H)
    body_layer, geom = _body_silhouette(W, H, size)
    composite = Image.alpha_composite(bg.convert("RGBA"), body_layer)
    dress_img = Image.open(io.BytesIO(dress_bytes))
    composite = _apply_dress(composite, dress_img, geom, fabric, colour_filter)
    final = _add_room_effects(composite, W, H)
    final = _watermark(final, W, H)
    out = io.BytesIO()
    final.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()
