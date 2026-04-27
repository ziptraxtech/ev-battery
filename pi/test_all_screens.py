#!/usr/bin/env python3
"""Quick smoke-test: show sample data on all 3 screens."""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from display.triple_lcd import TripleLCD
from display.widgets import gas_screen, temperature_screen, current_screen

cfg = {
    "display": {
        "screens": [
            {"id": 0, "label": "GAS",     "width": 240, "height": 240,
             "driver": "ST7789", "spi_port": 1, "cs": 0,
             "dc_pin": 22, "rst_pin": 27, "backlight_pin": 19, "rotation": 0},
            {"id": 1, "label": "TEMP",    "width": 160, "height": 80,
             "driver": "ST7735", "spi_port": 0, "cs": 0,
             "dc_pin": 4, "rst_pin": 24, "backlight_pin": 13, "rotation": 1,
             "offset_left": 26, "offset_top": 1, "bgr": True},
            {"id": 2, "label": "CURRENT", "width": 160, "height": 80,
             "driver": "ST7735", "spi_port": 0, "cs": 1,
             "dc_pin": 5, "rst_pin": 23, "backlight_pin": 12, "rotation": 1,
             "offset_left": 26, "offset_top": 1, "bgr": True},
        ]
    }
}

print("Initialising all 3 screens...")
lcd = TripleLCD(cfg)
print("Done. Rendering sample data...")

img0 = gas_screen(850, "warning",
                  temp_c=42.5, temp_status="ok",
                  current_a=35.2, voltage_v=52.1)

img1 = temperature_screen(42.5, "ok", gas_ppm=850, gas_status="warning")
img2 = current_screen(35.2, 52.1, 35.2 * 52.1, max_a=100.0)

lcd.show_all([img0, img1, img2])
print("All 3 screens updated. Check the display!")
print("Ctrl+C to exit.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
