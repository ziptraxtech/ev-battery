#!/usr/bin/env python3
"""Quick color test using raw ST7789 driver (spidev + RPi.GPIO)."""
import sys, time
sys.path.insert(0, "/home/zipsure-ai/repo/pi")
from display.raw_st7789 import RawST7789
from PIL import Image

d = RawST7789(
    width=240, height=240, rotation=0,
    port=1, cs=0, dc=22, rst=27, backlight=19,
    spi_speed_hz=10_000_000,
)
print("Init OK")

for color, name in [((255,0,0),"RED"), ((0,255,0),"GREEN"), ((0,0,255),"BLUE")]:
    d.display(Image.new("RGB", (240, 240), color))
    ans = input(f"  {name} visible? [y/n]: ").strip().lower()
    if ans == "y":
        print(f"SUCCESS — raw ST7789 works with {name}")
        break
else:
    print("Nothing visible — check wiring/SPI1 overlay")

d.cleanup()
