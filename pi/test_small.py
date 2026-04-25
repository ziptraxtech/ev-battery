#!/usr/bin/env python3
"""ST7735 0.96" small screen diagnostic — Waveshare Zero LCD HAT (A).
Tests all viable rotation / offset / size combos.
Screen 1 should show RED, Screen 2 should show GREEN — solid, no noise.
"""
import gc, time
from PIL import Image
import st7735

# ── Configs to test ───────────────────────────────────────────────────────────
# (label, width, height, rotation, offset_left, offset_top, bgr)
# Key insight: the ST7735 controller is 162x132 but the physical panel is 160x80.
# For landscape, offset_left=26,offset_top=1 is often needed with rotation=1 or 3.
CONFIGS = [
    # ── rotation=1 (90°, landscape) ──────────────────────────────────────────
    ("r=1 160x80  off 0/0  BGR",  160, 80, 1,  0,  0, True),
    ("r=1 160x80  off 1/26 BGR",  160, 80, 1,  1, 26, True),
    ("r=1 160x80  off 26/1 BGR",  160, 80, 1, 26,  1, True),
    ("r=1 160x80  off 24/0 BGR",  160, 80, 1, 24,  0, True),
    ("r=1 160x80  off 0/24 BGR",  160, 80, 1,  0, 24, True),
    # ── rotation=3 (270°, landscape) ─────────────────────────────────────────
    ("r=3 160x80  off 0/0  BGR",  160, 80, 3,  0,  0, True),
    ("r=3 160x80  off 1/26 BGR",  160, 80, 3,  1, 26, True),
    ("r=3 160x80  off 26/1 BGR",  160, 80, 3, 26,  1, True),
    ("r=3 160x80  off 24/0 BGR",  160, 80, 3, 24,  0, True),
    # ── rotation=0/2 (was tested before — noise; included for comparison) ────
    ("r=0 160x80  off 0/0  BGR",  160, 80, 0,  0,  0, True),
    ("r=0 160x80  off 1/26 BGR",  160, 80, 0,  1, 26, True),
    ("r=2 160x80  off 1/26 BGR",  160, 80, 2,  1, 26, True),
    # ── portrait native then rotated ─────────────────────────────────────────
    ("r=1 80x160  off 1/26 BGR",   80, 160, 1,  1, 26, True),
    ("r=3 80x160  off 1/26 BGR",   80, 160, 3,  1, 26, True),
    # ── RGB variants ─────────────────────────────────────────────────────────
    ("r=1 160x80  off 26/1 RGB",  160, 80, 1, 26,  1, False),
    ("r=1 160x80  off 1/26 RGB",  160, 80, 1,  1, 26, False),
]

# ── Shared pin config ─────────────────────────────────────────────────────────
SCREEN1 = dict(port=0, cs=0, dc=4,  rst=24, backlight=13, spi_speed_hz=20_000_000)
SCREEN2 = dict(port=0, cs=1, dc=5,  rst=23, backlight=12, spi_speed_hz=20_000_000)

total = len(CONFIGS)
for i, (label, w, h, rot, off_l, off_t, bgr) in enumerate(CONFIGS, 1):
    print(f"\nConfig {i}/{total}: {label}")
    d1 = d2 = None
    try:
        kw = dict(width=w, height=h, rotation=rot,
                  offset_left=off_l, offset_top=off_t, bgr=bgr)
        d1 = st7735.ST7735(**kw, **SCREEN1)
        d2 = st7735.ST7735(**kw, **SCREEN2)

        red   = Image.new("RGB", (w, h), (255,   0,   0))
        green = Image.new("RGB", (w, h), (  0, 255,   0))
        d1.display(red)
        d2.display(green)

        ans = input("  Screen1=RED solid, Screen2=GREEN solid? [y/n/skip]: ").strip().lower()
        if ans == "y":
            print(f"\n*** WORKING CONFIG: {label} ***")
            print(f"    width={w}, height={h}, rotation={rot},")
            print(f"    offset_left={off_l}, offset_top={off_t}, bgr={bgr}")
            break
    except Exception as e:
        print(f"  FAILED: {e}")
    finally:
        del d1, d2
        gc.collect()
        time.sleep(0.5)
else:
    print("\nNo working config found.")
    print("Check wiring:")
    print("  Screen1: port=0 cs=CE0 dc=GPIO4  rst=GPIO24 bl=GPIO13")
    print("  Screen2: port=0 cs=CE1 dc=GPIO5  rst=GPIO23 bl=GPIO12")

print("\nDone.")
