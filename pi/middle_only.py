#!/usr/bin/env python3
"""Run only the middle 1.3" screen with live sensor data. Small screens off."""
import time, threading, json, signal, sys
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont

# Turn off small screen backlights
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
for pin in (13, 12):
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Use raw ST7789 driver (spidev + RPi.GPIO) — avoids gpiod/SPI1 MISO conflict
sys.path.insert(0, "/home/zipsure-ai/repo/pi")
from display.raw_st7789 import RawST7789
import serial

mid = RawST7789(
    width=240, height=240, rotation=0,
    port=1, cs=0, dc=22, rst=27, backlight=19,
    spi_speed_hz=40_000_000,
)

try:
    font_lg = ImageFont.truetype("/home/zipsure-ai/repo/pi/display/fonts/RobotoMono-Bold.ttf",    44)
    font_md = ImageFont.truetype("/home/zipsure-ai/repo/pi/display/fonts/RobotoMono-Regular.ttf", 20)
    font_sm = ImageFont.truetype("/home/zipsure-ai/repo/pi/display/fonts/RobotoMono-Regular.ttf", 15)
except Exception:
    font_lg = font_md = font_sm = ImageFont.load_default()

DARK   = (15,  15,  15)
WHITE  = (255, 255, 255)
GREEN  = (0,   200,  70)
YELLOW = (255, 210,   0)
BLUE   = (40,  130, 255)
RED    = (220,  30,  30)
GREY   = (90,   90,  90)

latest = {}
lock   = threading.Lock()
running = True

def read_serial():
    while running:
        try:
            ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=2)
            while running:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    try:
                        data = json.loads(line)
                        if "gas_ppm" in data:
                            with lock:
                                latest.update(data)
                    except Exception:
                        pass
        except Exception:
            time.sleep(3)

threading.Thread(target=read_serial, daemon=True).start()

def render():
    with lock:
        d = dict(latest)

    img = Image.new("RGB", (240, 240), DARK)
    draw = ImageDraw.Draw(img)

    # Header
    draw.text((120, 18), "ZipSure EV", font=font_sm, fill=GREY, anchor="mm")
    draw.line([(10, 34), (230, 34)], fill=GREY, width=1)

    if not d:
        draw.text((120, 120), "NO DATA", font=font_md, fill=RED, anchor="mm")
        draw.text((120, 150), "Waiting for ESP32", font=font_sm, fill=GREY, anchor="mm")
    else:
        gas  = d.get("gas_ppm", -1)
        temp = d.get("temp_c", -999)
        curr = d.get("current_a")
        volt = d.get("voltage_v")
        alts = d.get("alerts", [])

        # Gas
        g_col = RED if "GAS_CRITICAL" in alts else YELLOW if "GAS_WARNING" in alts else GREEN
        draw.text((12, 55),  "CO₂",            font=font_sm, fill=GREY)
        draw.text((228, 55), f"{gas} ppm" if gas >= 0 else "---", font=font_sm, fill=g_col, anchor="ra")

        # Temp
        t_col = RED if "TEMP_CRITICAL" in alts else YELLOW if "TEMP_WARNING" in alts else GREEN
        draw.text((12, 90),  "TEMP",            font=font_sm, fill=GREY)
        draw.text((228, 90), f"{temp:.1f} C" if temp > -900 else "---", font=font_sm, fill=t_col, anchor="ra")

        # Current (big)
        cur_str = f"{curr:.1f} A" if curr is not None else "--- A"
        draw.text((120, 150), cur_str, font=font_lg, fill=BLUE, anchor="mm")

        # Voltage / Power
        v_str = f"{volt:.1f}V" if volt and volt > 0 else "--V"
        p_str = f"{volt*curr:.0f}W" if (volt and curr and volt > 0 and curr > 0) else "--W"
        draw.text((60,  200), v_str, font=font_md, fill=WHITE,  anchor="mm")
        draw.text((180, 200), p_str, font=font_md, fill=YELLOW, anchor="mm")

        # Alert bar
        if alts:
            draw.rectangle([0, 220, 240, 240], fill=RED)
            draw.text((120, 230), "  ".join(alts), font=font_sm, fill=WHITE, anchor="mm")

    mid.display(img)

def shutdown(sig, frame):
    global running
    running = False
    mid.cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT,  shutdown)
signal.signal(signal.SIGTERM, shutdown)

print("Middle screen running. Ctrl+C to stop.")
while running:
    render()
    time.sleep(1)
