#!/usr/bin/env python3
"""ST7789 1.3" middle screen diagnostic — Waveshare Zero LCD HAT (A)."""
import os, sys, time, gc, subprocess
from PIL import Image

# Force RST (GPIO27) HIGH before any library touches it.
# A previous process exit may leave RST LOW (display stuck in hardware reset).
print("Pre-driving RST (GPIO27) HIGH via pinctrl...")
subprocess.run(["pinctrl", "set", "27", "op", "dh"], check=False, capture_output=True)
time.sleep(0.15)

if not os.path.exists("/dev/spidev1.0"):
    sys.exit("ERROR: /dev/spidev1.0 not found — is dtoverlay=spi1-1cs in /boot/firmware/config.txt?")

import st7789

RED  = Image.new("RGB", (240, 240), (255,   0,   0))
GRN  = Image.new("RGB", (240, 240), (  0, 255,   0))
BLU  = Image.new("RGB", (240, 240), (  0,   0, 255))
WHT  = Image.new("RGB", (240, 240), (255, 255, 255))
COLORS = [(RED, "RED"), (GRN, "GREEN"), (BLU, "BLUE"), (WHT, "WHITE")]

BASE = dict(width=240, height=240, port=1, cs=0, dc=22, backlight=19)

CONFIGS = [
    ("no RST, rotation=0, 40MHz",   dict(**BASE, rotation=0,   spi_speed_hz=40_000_000)),
    ("RST=27, rotation=0, 40MHz",   dict(**BASE, rotation=0,   rst=27, spi_speed_hz=40_000_000)),
    ("RST=27, rotation=0, 20MHz",   dict(**BASE, rotation=0,   rst=27, spi_speed_hz=20_000_000)),
    ("RST=27, rotation=90, 40MHz",  dict(**BASE, rotation=90,  rst=27, spi_speed_hz=40_000_000)),
    ("RST=27, rotation=180, 40MHz", dict(**BASE, rotation=180, rst=27, spi_speed_hz=40_000_000)),
    ("RST=27, rotation=270, 40MHz", dict(**BASE, rotation=270, rst=27, spi_speed_hz=40_000_000)),
]

for label, cfg in CONFIGS:
    print(f"\n{'─'*55}\nConfig: {label}")
    d = None
    try:
        d = st7789.ST7789(**cfg)
        for img, name in COLORS:
            d.display(img)
            print(f"  -> {name} sent (1.5s)")
            time.sleep(1.5)
        ans = input("  Any color visible on screen? [y/N]: ").strip().lower()
        if ans == "y":
            print(f"\n*** WORKING CONFIG: {label} ***")
            print(f"    {cfg}")
            break
    except Exception as e:
        print(f"  FAILED: {e}")
    finally:
        del d
        gc.collect()
        time.sleep(0.3)
else:
    print("\nAll configs failed — check wiring:")
    print("  GPIO18=CS  GPIO20=MOSI  GPIO21=SCLK  GPIO22=DC  GPIO27=RST  GPIO19=BL")
    print("  Run: pinctrl get 18,19,20,21,22,27")

print("\nDone.")
