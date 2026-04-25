#!/usr/bin/env python3
"""
Color test for ST7735 offset/BGR diagnosis.
Draws solid red on Screen 1, solid green on Screen 2.
- If Screen shows BLUE instead of RED → needs bgr=True
- If color appears in wrong position → needs offset adjustment
"""
from PIL import Image
import st7735, time

CONFIGS = [
    # (label, offset_left, offset_top, bgr)
    ("no offset, RGB",     0,  0,  False),
    ("offset 1/24, RGB",   1, 24,  False),
    ("offset 1/26, RGB",   1, 26,  False),
    ("offset 0/24, RGB",   0, 24,  False),
    ("offset 1/24, BGR",   1, 24,  True),
]

red   = Image.new("RGB", (160, 80), (255,   0,   0))
green = Image.new("RGB", (160, 80), (  0, 255,   0))

for label, off_l, off_t, bgr in CONFIGS:
    print(f"\nTrying: {label}")
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
        input("  → Screen 1 should be RED, Screen 2 GREEN. Correct? (Enter to try next) ")
    except Exception as e:
        print(f"  FAILED: {e}")
