#!/usr/bin/env python3
import subprocess, time
from PIL import Image
import st7789

subprocess.run(["pinctrl", "set", "27", "op", "dh"], capture_output=True)
subprocess.run(["pinctrl", "set", "19", "op", "dh"], capture_output=True)
time.sleep(0.1)

d = st7789.ST7789(
    width=240, height=240, rotation=0,
    port=1, cs=0, dc=22, rst=27, backlight=None,
    spi_speed_hz=10_000_000,
)
print("Init OK")

for color, name in [((255,0,0),"RED"), ((0,255,0),"GREEN"), ((0,0,255),"BLUE")]:
    d.display(Image.new("RGB", (240, 240), color))
    ans = input(f"  {name} visible? [y/n]: ").strip().lower()
    if ans == "y":
        print(f"SUCCESS — Pimoroni ST7789 works with {name}")
        break
else:
    print("Nothing visible — SPI1 or init issue")
