"""
Widget renderers for Waveshare Zero LCD HAT (A) — bar-gauge style.

Screen 0 — 240×240  ST7789  — ZipSure main dashboard
Screen 1 — 160×80   ST7735  — CO₂ + Temperature (dual vertical bars)
Screen 2 — 160×80   ST7735  — Current + Voltage  (dual vertical bars)
"""

import os
from PIL import Image, ImageDraw, ImageFont

_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Try project fonts → DejaVu system font → PIL default."""
    for path in [
        os.path.join(_FONT_DIR, name),
        f"/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        f"/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

# Fonts for 240×240 main screen
F_TITLE  = _font("RobotoMono-Bold.ttf",    18)
F_LARGE  = _font("RobotoMono-Bold.ttf",    52)
F_MED    = _font("RobotoMono-Regular.ttf", 20)
F_SMALL  = _font("RobotoMono-Regular.ttf", 14)
F_MINI   = _font("RobotoMono-Regular.ttf", 11)

# Fonts for 160×80 small screens
F_BAR_LBL = _font("RobotoMono-Regular.ttf", 10)
F_BAR_VAL = _font("RobotoMono-Bold.ttf",    13)

# Data colours (same in both themes)
GREEN   = (0,   210,  70)
YELLOW  = (255, 210,   0)
RED     = (220,  30,  30)
CYAN    = (0,   200, 220)
ORANGE  = (255, 140,   0)
BLUE    = (40,  130, 255)
PURPLE  = (160,  50, 240)

# Theme-aware palette — reassigned by set_theme()
DARK   = (12,  12,  12)
WHITE  = (255, 255, 255)
GREY   = (85,  85,  85)
DIM    = (40,  40,  40)

_THEMES = {
    "dark":  {"DARK": (12,12,12),    "WHITE": (255,255,255), "GREY": (85,85,85),   "DIM": (40,40,40)},
    "light": {"DARK": (230,230,230), "WHITE": (20,20,20),    "GREY": (130,130,130),"DIM": (180,180,180)},
}

def set_theme(name: str):
    """Switch between 'dark' and 'light' themes."""
    global DARK, WHITE, GREY, DIM
    t = _THEMES.get(name, _THEMES["dark"])
    DARK, WHITE, GREY, DIM = t["DARK"], t["WHITE"], t["GREY"], t["DIM"]


def _status_color(level: str) -> tuple:
    return {"ok": GREEN, "warning": YELLOW, "critical": RED}.get(level, WHITE)


def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _vbar(draw, cx, top_y, w, h, fraction,
          color_lo=(0, 210, 70), color_hi=(220, 30, 30)):
    """
    Draw a vertical bar gauge centered at cx.
    Fills from the bottom upward; gradient from color_lo (bottom) to color_hi (top).
    """
    x0, x1 = cx - w // 2, cx + w // 2
    y0, y1 = top_y, top_y + h

    # Container
    draw.rectangle([x0, y0, x1, y1], fill=(22, 22, 22))
    draw.rectangle([x0, y0, x1, y1], outline=(55, 55, 55))

    frac  = max(0.0, min(1.0, fraction))
    fill_h = int(h * frac)
    if fill_h < 1:
        return

    fill_y0 = y1 - fill_h
    for row in range(fill_h):
        t = row / max(fill_h - 1, 1)
        color = _lerp(color_lo, color_hi, t)
        draw.line([(x0 + 1, fill_y0 + row), (x1 - 1, fill_y0 + row)], fill=color)


# ── Small-screen dual-bar helper ─────────────────────────────────────────────

BAR_W   = 28   # bar width  (pixels)
BAR_H   = 46   # bar height (pixels)
BAR_TOP = 13   # y-start of bars
LBL_Y   = 4    # y-start of label
VAL_Y   = BAR_TOP + BAR_H + 3  # y-start of value text


def _dual_bar_screen(
    left_label,  left_val_str,  left_frac,  left_lo,  left_hi,
    right_label, right_val_str, right_frac, right_lo, right_hi,
) -> Image.Image:
    img  = Image.new("RGB", (160, 80), DARK)
    d    = ImageDraw.Draw(img)

    # Divider
    d.line([(80, 4), (80, 76)], fill=(40, 40, 40))

    for cx, label, val_str, frac, c_lo, c_hi in [
        (40,  left_label,  left_val_str,  left_frac,  left_lo,  left_hi),
        (120, right_label, right_val_str, right_frac, right_lo, right_hi),
    ]:
        # Label
        d.text((cx, LBL_Y), label, font=F_BAR_LBL, fill=GREY, anchor="mt")

        # Vertical bar
        _vbar(d, cx, BAR_TOP, BAR_W, BAR_H, frac, c_lo, c_hi)

        # Value
        d.text((cx, VAL_Y), val_str, font=F_BAR_VAL, fill=WHITE, anchor="mt")

    return img


# ── Screen 1 — CO₂ + Temperature (160×80) ────────────────────────────────────

def temperature_screen(temp_c: float | None, status: str,
                       gas_ppm: int | None = None, gas_status: str = "ok") -> Image.Image:
    # CO₂ bar: 0–3000 ppm, green→red
    gas_frac = (gas_ppm or 0) / 3000.0 if gas_ppm and gas_ppm >= 0 else 0.0
    gas_str  = f"{gas_ppm}p"  if (gas_ppm is not None and gas_ppm >= 0) else "--p"

    # Temp bar: 0–80°C, cyan→red
    temp_frac = max(0.0, (temp_c or 0) / 80.0) if temp_c and temp_c > -900 else 0.0
    temp_str  = f"{temp_c:.0f}C" if (temp_c is not None and temp_c > -900) else "--C"

    return _dual_bar_screen(
        "CO2",  gas_str,  gas_frac,  GREEN,  RED,
        "TEMP", temp_str, temp_frac, CYAN,   RED,
    )


# ── Screen 2 — Current + Voltage (160×80) ────────────────────────────────────

def current_screen(current_a: float | None, voltage_v: float | None,
                   power_w: float | None, max_a: float = 100.0) -> Image.Image:
    # Current bar: 0–max_a, cyan→orange
    cur_frac = (abs(current_a) / max_a) if current_a is not None else 0.0
    cur_str  = f"{current_a:.0f}A" if current_a is not None else "--A"

    # Voltage bar: 40–60V mapped to 0–1, blue→green
    V_MIN, V_MAX = 40.0, 60.0
    v_frac = max(0.0, min(1.0, ((voltage_v or V_MIN) - V_MIN) / (V_MAX - V_MIN))) \
             if voltage_v and voltage_v > 0 else 0.0
    v_str  = f"{voltage_v:.0f}V" if (voltage_v and voltage_v > 0) else "--V"

    return _dual_bar_screen(
        "AMP",  cur_str, cur_frac, CYAN, ORANGE,
        "VOLT", v_str,   v_frac,   BLUE, GREEN,
    )


# ── Screen 0 — Main ZipSure dashboard (240×240) ───────────────────────────────

def gas_screen(ppm: int | None, status: str,
               temp_c: float | None = None, temp_status: str = "ok",
               current_a: float | None = None, voltage_v: float | None = None) -> Image.Image:
    img = Image.new("RGB", (240, 240), DARK)
    d   = ImageDraw.Draw(img)

    # ── Header ────────────────────────────────────────────────────────────────
    d.text((120, 14), "ZipSure EV", font=F_TITLE, fill=GREY, anchor="mm")
    d.line([(10, 26), (230, 26)], fill=DIM, width=1)

    # ── CO₂ — big number ─────────────────────────────────────────────────────
    col_gas = _status_color(status)
    val_str = f"{ppm}" if (ppm is not None and ppm >= 0) else "---"
    d.text((120,  78), val_str, font=F_LARGE, fill=col_gas, anchor="mm")
    d.text((120, 108), "ppm  CO₂",  font=F_SMALL, fill=WHITE,   anchor="mm")

    # Horizontal bar (0–3000 ppm)
    bw = 180
    bx = (240 - bw) // 2
    d.rectangle([bx, 120, bx + bw, 132], fill=DIM)
    fw = int(bw * min(1.0, (ppm or 0) / 3000.0))
    if fw:
        d.rectangle([bx, 120, bx + fw, 132], fill=col_gas)

    # Status pill
    d.rounded_rectangle([70, 138, 170, 158], radius=7, fill=col_gas)
    d.text((120, 148), status.upper(), font=F_MINI, fill=DARK, anchor="mm")

    # ── Secondary metrics ─────────────────────────────────────────────────────
    d.line([(10, 166), (230, 166)], fill=DIM, width=1)

    col_t = _status_color(temp_status)
    t_str = f"{temp_c:.1f}°C" if (temp_c is not None and temp_c > -900) else "---°C"
    c_str = f"{current_a:.1f}A" if current_a is not None else "---A"
    v_str = f"{voltage_v:.1f}V" if (voltage_v and voltage_v > 0) else "---V"

    d.text((12,  178), "TEMP",    font=F_MINI,  fill=GREY)
    d.text((12,  194), t_str,     font=F_SMALL, fill=col_t)

    d.text((88,  178), "CURRENT", font=F_MINI,  fill=GREY)
    d.text((88,  194), c_str,     font=F_SMALL, fill=BLUE)

    d.text((168, 178), "VOLT",    font=F_MINI,  fill=GREY)
    d.text((168, 194), v_str,     font=F_SMALL, fill=GREEN)

    # ── Alert bar ─────────────────────────────────────────────────────────────
    if status != "ok" or temp_status != "ok":
        worst = "critical" if "critical" in (status, temp_status) else "warning"
        bar_col = RED if worst == "critical" else YELLOW
        d.rectangle([0, 218, 240, 240], fill=bar_col)
        msg = "CRITICAL ALERT" if worst == "critical" else "WARNING"
        d.text((120, 229), msg, font=F_MINI, fill=DARK, anchor="mm")

    return img


# ── Offline fallback ──────────────────────────────────────────────────────────

def offline_screen(label: str, size: tuple = (240, 240)) -> Image.Image:
    img = Image.new("RGB", size, DARK)
    d   = ImageDraw.Draw(img)
    cx, cy = size[0] // 2, size[1] // 2
    font = F_SMALL if size[0] >= 200 else F_BAR_LBL
    d.text((cx, cy - 10), label,     font=font, fill=GREY, anchor="mm")
    d.text((cx, cy + 10), "NO DATA", font=font, fill=RED,  anchor="mm")
    return img
