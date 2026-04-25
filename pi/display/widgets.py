"""
Widget renderers for the Waveshare Zero LCD HAT (A).

Screen 0 — 240×240  (1.3"  ST7789) — Gas/CO2
Screen 1 — 160×80   (0.96" ST7735) — Temperature
Screen 2 — 160×80   (0.96" ST7735) — Current / Power
"""

import os
from PIL import Image, ImageDraw, ImageFont

_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(os.path.join(_FONT_DIR, name), size)
    except Exception:
        return ImageFont.load_default()

# Font sizes tuned per screen
F_LARGE  = _font("RobotoMono-Bold.ttf",    48)   # 240×240 big value
F_MED    = _font("RobotoMono-Regular.ttf", 22)
F_SMALL  = _font("RobotoMono-Regular.ttf", 15)
F_MINI   = _font("RobotoMono-Regular.ttf", 13)

# Smaller fonts for the 160×80 screens
F_SM_VAL = _font("RobotoMono-Bold.ttf",    32)
F_SM_LBL = _font("RobotoMono-Regular.ttf", 14)
F_SM_UNT = _font("RobotoMono-Regular.ttf", 12)

# Palette
DARK   = (15,  15,  15)
WHITE  = (255, 255, 255)
GREY   = (90,  90,  90)
GREEN  = (0,   200,  70)
YELLOW = (255, 210,   0)
RED    = (220,  30,  30)
BLUE   = (40,  130, 255)
BLACK  = (0,    0,   0)


def _status_color(level: str) -> tuple:
    return {"ok": GREEN, "warning": YELLOW, "critical": RED}.get(level, WHITE)


def _bar(draw, x, y, w, h, fraction, color, bg=GREY):
    draw.rectangle([x, y, x + w, y + h], fill=bg)
    fw = int(w * max(0.0, min(1.0, fraction)))
    if fw > 0:
        draw.rectangle([x, y, x + fw, y + h], fill=color)


# ── Screen 0 — Gas sensor (240×240) ──────────────────────────────────────────

def gas_screen(ppm: int | None, status: str) -> Image.Image:
    img = Image.new("RGB", (240, 240), DARK)
    d   = ImageDraw.Draw(img)
    col = _status_color(status)

    d.text((12, 8),   "CO₂ / GAS", font=F_SMALL, fill=GREY)

    val = f"{ppm}" if (ppm is not None and ppm >= 0) else "---"
    d.text((120, 100), val,   font=F_LARGE, fill=col,   anchor="mm")
    d.text((120, 148), "ppm", font=F_MED,   fill=WHITE, anchor="mm")

    # Bar 0–3000 ppm
    _bar(d, 20, 172, 200, 14, (ppm or 0) / 3000.0, col)

    # Status pill
    pill_col = col if status != "ok" else DARK
    d.rounded_rectangle([55, 196, 185, 224], radius=8, fill=pill_col)
    txt_col = BLACK if status in ("warning", "critical") else col
    d.text((120, 210), status.upper(), font=F_SMALL, fill=txt_col, anchor="mm")

    return img


# ── Screen 1 — Temperature (160×80) ──────────────────────────────────────────

def temperature_screen(temp_c: float | None, status: str) -> Image.Image:
    img = Image.new("RGB", (160, 80), DARK)
    d   = ImageDraw.Draw(img)
    col = _status_color(status)

    d.text((6, 4), "TEMP", font=F_SM_LBL, fill=GREY)

    val = f"{temp_c:.1f}" if (temp_c is not None and temp_c > -900) else "---"
    d.text((80, 36), val,  font=F_SM_VAL, fill=col,   anchor="mm")
    d.text((80, 60), "°C", font=F_SM_UNT, fill=WHITE, anchor="mm")

    # Thin bar along bottom (0–80°C)
    _bar(d, 6, 72, 148, 5, (temp_c or 0) / 80.0, col)

    return img


# ── Screen 2 — Current / Power (160×80) ──────────────────────────────────────

def current_screen(current_a: float | None, voltage_v: float | None,
                   power_w: float | None, max_a: float = 100.0) -> Image.Image:
    img = Image.new("RGB", (160, 80), DARK)
    d   = ImageDraw.Draw(img)

    d.text((6, 4), "CURRENT", font=F_SM_LBL, fill=GREY)

    cur = f"{current_a:.1f}A" if current_a is not None else "---"
    d.text((80, 30), cur, font=F_SM_VAL, fill=BLUE, anchor="mm")

    # Bar
    _bar(d, 6, 50, 148, 5, (abs(current_a) if current_a else 0) / max_a, BLUE)

    # Voltage and power on one line
    v_str = f"{voltage_v:.0f}V" if (voltage_v and voltage_v > 0) else "--V"
    p_str = f"{power_w:.0f}W"   if (power_w   and power_w  > 0) else "--W"
    d.text((6,  62), v_str, font=F_SM_UNT, fill=WHITE)
    d.text((90, 62), p_str, font=F_SM_UNT, fill=YELLOW)

    return img


# ── Offline fallback ──────────────────────────────────────────────────────────

def offline_screen(label: str, size: tuple = (240, 240)) -> Image.Image:
    img = Image.new("RGB", size, DARK)
    d   = ImageDraw.Draw(img)
    cx, cy = size[0] // 2, size[1] // 2
    font = F_SMALL if size[0] >= 200 else F_SM_LBL
    d.text((cx, cy - 10), label,     font=font, fill=GREY, anchor="mm")
    d.text((cx, cy + 12), "NO DATA", font=font, fill=RED,  anchor="mm")
    return img
