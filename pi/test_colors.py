#!/usr/bin/env python3
"""
Color test for ST7735 offset/BGR diagnosis.
Draws solid red on Screen 1, solid green on Screen 2.
- RED shown as BLUE → needs bgr=True
- White noise on edges → wrong offset
"""
import gc
from PIL import Image
import st7735

CONFIGS = [
    # (label,              offset_left, offset_top, bgr)
    ("no offset, RGB",     0,  0,  False),
    ("offset 1/24, RGB",   1, 24,  False),
    ("offset 1/26, RGB",   1, 26,  False),
    ("offset 0/24, RGB",   0, 24,  False),
    ("offset 1/24, BGR",   1, 24,  True),
    ("offset 0/24, BGR",   0, 24,  True),
    ("offset 1/26, BGR",   1, 26,  True),
]

red   = Image.new("RGB", (160, 80), (255,   0,   0))
green = Image.new("RGB", (160, 80), (  0, 255,   0))

for i, (label, off_l, off_t, bgr) in enumerate(CONFIGS, 1):
    print(f"\nConfig {i}/{len(CONFIGS)}: {label}")
    d1 = d2 = None
    try:
        d1 = st7735.ST7735(
            width=160, height=80, rotation=0,
            port=0, cs=0, dc=4, rst=24, backlight=13,
            offset_left=off_l, offset_top=off_t,
            bgr=bgr, spi_speed_hz=20000000,
        )
        d2 = st7735.ST7735(
            width=160, height=80, rotation=0,
            port=0, cs=1, dc=5, rst=23, backlight=12,
            offset_left=off_l, offset_top=off_t,
            bgr=bgr, spi_speed_hz=20000000,
        )
        d1.display(red)
        d2.display(green)
        input("  Screen 1=RED, Screen 2=GREEN? Any noise? (Enter to continue) ")
    except Exception as e:
        print(f"  FAILED: {e}")
    finally:
        # Release SPI/GPIO before next config
        del d1
        del d2
        gc.collect()

print("\nDone. Tell me which config number looked cleanest.")
