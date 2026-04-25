#!/usr/bin/env python3
"""Quick display init test — run on Pi to get full traceback."""
import traceback

print("Testing st7789 (Screen 0 — SPI1)...")
try:
    import st7789
    d = st7789.ST7789(
        width=240, height=240, rotation=0,
        port=1, cs=0, dc=22, rst=27, backlight=19,   # cs=CE index, not GPIO pin
        spi_speed_hz=40000000,
    )
    print("  Screen 0 OK")
except Exception:
    print("  Screen 0 FAILED:")
    traceback.print_exc()

print("\nTesting st7735 (Screen 1 — SPI0 CE0)...")
try:
    import st7735
    d = st7735.ST7735(
        width=160, height=80, rotation=0,
        port=0, cs=0, dc=4, rst=24, backlight=13,   # CE0
        spi_speed_hz=40000000,
    )
    print("  Screen 1 OK")
except Exception:
    print("  Screen 1 FAILED:")
    traceback.print_exc()

print("\nTesting st7735 (Screen 2 — SPI0 CE1)...")
try:
    d = st7735.ST7735(
        width=160, height=80, rotation=0,
        port=0, cs=1, dc=5, rst=23, backlight=12,   # CE1
        spi_speed_hz=40000000,
    )
    print("  Screen 2 OK")
except Exception:
    print("  Screen 2 FAILED:")
    traceback.print_exc()
