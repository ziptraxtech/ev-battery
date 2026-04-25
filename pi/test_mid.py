#!/usr/bin/env python3
"""Diagnose ST7789 blank screen — test RST pin behaviour."""
from PIL import Image
import st7789, time

red  = Image.new("RGB", (240, 240), (255, 0, 0))
blue = Image.new("RGB", (240, 240), (0, 0, 255))

# ── Test 1: no RST pin (let display use its own power-on state) ───────────────
print("Test 1 — no rst pin...")
try:
    mid = st7789.ST7789(
        width=240, height=240, rotation=0,
        port=1, cs=0, dc=22, backlight=19,
        spi_speed_hz=40000000,
        # rst omitted intentionally
    )
    mid.display(red)
    input("  Screen RED? (Enter to continue) ")
except Exception as e:
    print(f"  FAILED: {e}")

# ── Test 2: with RST, but call reset() manually before display ────────────────
print("\nTest 2 — with rst=27, explicit reset() call...")
try:
    mid = st7789.ST7789(
        width=240, height=240, rotation=0,
        port=1, cs=0, dc=22, rst=27, backlight=19,
        spi_speed_hz=40000000,
    )
    mid.reset()     # toggle RST HIGH→LOW→HIGH
    mid._init()     # re-run init after hardware reset
    mid.display(blue)
    input("  Screen BLUE? (Enter to end) ")
except Exception as e:
    print(f"  FAILED: {e}")

print("Done.")
