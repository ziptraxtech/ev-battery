#!/usr/bin/env python3
"""
ST7735 rotation + offset diagnostic for Waveshare Zero LCD HAT (A) 0.96" screens.
Look at Screen 1 (top) and Screen 2 (bottom) for each config.
Best config = solid RED on Screen 1, solid GREEN on Screen 2, no noise.
"""
import gc
from PIL import Image
import st7735

CONFIGS = [
    # (label,                    rot, offset_left, offset_top, bgr)
    ("rot=0,  no offset, BGR",    0,  0,  0,  True),
    ("rot=0,  offset 1/24, BGR",  0,  1, 24,  True),
    ("rot=0,  offset 0/24, BGR",  0,  0, 24,  True),
    ("rot=0,  offset 1/26, BGR",  0,  1, 26,  True),
    ("rot=2,  no offset, BGR",    2,  0,  0,  True),
    ("rot=2,  offset 1/24, BGR",  2,  1, 24,  True),
    ("rot=2,  offset 0/24, BGR",  2,  0, 24,  True),
    ("rot=2,  offset 1/26, BGR",  2,  1, 26,  True),
    ("rot=0,  no offset, RGB",    0,  0,  0,  False),
    ("rot=2,  no offset, RGB",    2,  0,  0,  False),
]

red   = Image.new("RGB", (160, 80), (255,   0,   0))
green = Image.new("RGB", (160, 80), (  0, 255,   0))

for i, (label, rot, off_l, off_t, bgr) in enumerate(CONFIGS, 1):
    print(f"\nConfig {i}/{len(CONFIGS)}: {label}")
    d1 = d2 = None
    try:
        d1 = st7735.ST7735(
            width=160, height=80, rotation=rot,
            port=0, cs=0, dc=4, rst=24, backlight=13,
            offset_left=off_l, offset_top=off_t,
            bgr=bgr, spi_speed_hz=20000000,
        )
        d2 = st7735.ST7735(
            width=160, height=80, rotation=rot,
            port=0, cs=1, dc=5, rst=23, backlight=12,
            offset_left=off_l, offset_top=off_t,
            bgr=bgr, spi_speed_hz=20000000,
        )
        d1.display(red)
        d2.display(green)
        ans = input("  Noise? Color correct? Enter config number if BEST, else just Enter: ")
        if ans.strip():
            print(f"  *** Marked as best: {label} ***")
    except Exception as e:
        print(f"  FAILED: {e}")
    finally:
        del d1, d2
        gc.collect()

print("\nDone.")
