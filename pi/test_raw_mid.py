#!/usr/bin/env python3
"""Raw SPI test for ST7789 — bypasses Pimoroni library entirely.
If this shows color but test_mid.py doesn't, the issue is the Pimoroni init sequence.
If this also shows nothing, the issue is hardware/wiring.
"""
import struct, subprocess, sys, time

try:
    import spidev
    import RPi.GPIO as GPIO
except ImportError as e:
    sys.exit(f"Missing library: {e}")

DC_PIN  = 22
BL_PIN  = 19
RST_PIN = 27

# ── Setup ──────────────────────────────────────────────────────────────────────
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(DC_PIN, GPIO.OUT)
GPIO.setup(BL_PIN, GPIO.OUT)
GPIO.output(BL_PIN, GPIO.HIGH)
print("Backlight ON (GPIO19 HIGH)")

# Hardware reset via pinctrl (avoids gpiod conflicts from previous runs)
print("Hardware reset (RST GPIO27)...")
subprocess.run(["pinctrl", "set", str(RST_PIN), "op", "dh"], capture_output=True)
time.sleep(0.05)
subprocess.run(["pinctrl", "set", str(RST_PIN), "op", "dl"], capture_output=True)
time.sleep(0.15)
subprocess.run(["pinctrl", "set", str(RST_PIN), "op", "dh"], capture_output=True)
time.sleep(0.20)
print("Reset done")

# ── SPI ────────────────────────────────────────────────────────────────────────
spi = spidev.SpiDev()
try:
    spi.open(1, 0)  # SPI1, CE0
except Exception as e:
    GPIO.cleanup()
    sys.exit(f"Cannot open /dev/spidev1.0: {e}")

spi.max_speed_hz = 10_000_000  # conservative 10 MHz
spi.mode = 0

def _cmd(c: int):
    GPIO.output(DC_PIN, GPIO.LOW)
    spi.writebytes([c])

def _data(d):
    GPIO.output(DC_PIN, GPIO.HIGH)
    spi.writebytes(list(d))

# ── ST7789 minimal init ────────────────────────────────────────────────────────
print("Sending ST7789 init sequence...")
_cmd(0x01); time.sleep(0.15)   # SWRESET
_cmd(0x11); time.sleep(0.12)   # SLPOUT
_cmd(0x3A); _data([0x55])      # COLMOD  16bpp RGB565
_cmd(0x36); _data([0x00])      # MADCTL  row/col normal
_cmd(0x21)                     # INVON   (most 240x240 ST7789 panels need this)
_cmd(0x13)                     # NORON
_cmd(0x29); time.sleep(0.05)   # DISPON
print("Init done")

# ── Fill screen ────────────────────────────────────────────────────────────────
def fill(r: int, g: int, b: int):
    r5 = (r >> 3) & 0x1F
    g6 = (g >> 2) & 0x3F
    b5 = (b >> 3) & 0x1F
    px = struct.pack(">H", (r5 << 11) | (g6 << 5) | b5)

    _cmd(0x2A); _data([0x00, 0x00, 0x00, 0xEF])  # CASET 0..239
    _cmd(0x2B); _data([0x00, 0x00, 0x00, 0xEF])  # RASET 0..239
    _cmd(0x2C)

    GPIO.output(DC_PIN, GPIO.HIGH)
    chunk = px * 512
    for _ in range(240 * 240 // 512):
        spi.writebytes2(chunk)
    rem = (240 * 240) % 512
    if rem:
        spi.writebytes2(px * rem)

COLORS = [
    ((255,   0,   0), "RED"),
    ((  0, 255,   0), "GREEN"),
    ((  0,   0, 255), "BLUE"),
    ((255, 255, 255), "WHITE"),
]

success = False
for (r, g, b), name in COLORS:
    print(f"\nFilling screen with {name}...")
    fill(r, g, b)
    ans = input(f"  {name} visible on screen? [y/N]: ").strip().lower()
    if ans == "y":
        print(f"\nSUCCESS — raw SPI works with {name}!")
        print("Conclusion: ST7789 hardware is fine.")
        print("Next step: the Pimoroni st7789 library init needs fixing for this panel.")
        success = True
        break

if not success:
    print("\nRaw SPI also shows nothing.")
    print("Hardware checks:")
    print("  Run: pinctrl get 18,19,20,21,22,27")
    print("  Expected:")
    print("    GPIO18 = output (CS, idle HIGH)")
    print("    GPIO19 = output HIGH (backlight)")
    print("    GPIO20 = ALT4 (SPI1 MOSI)")
    print("    GPIO21 = ALT4 (SPI1 SCLK)")
    print("    GPIO22 = output (DC)")
    print("    GPIO27 = output HIGH (RST, not in reset)")
    print("  If GPIO20/21 are NOT ALT4: SPI1 overlay missing")
    print("  If any pin is 'input': wiring or overlay issue")
    print("  Try running as root: sudo ./venv/bin/python test_raw_mid.py")

spi.close()
GPIO.cleanup()
print("\nDone.")
