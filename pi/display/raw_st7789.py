"""
Raw ST7789 driver using spidev + RPi.GPIO.
Bypasses Pimoroni/gpiod entirely — matches the approach confirmed working
in test_raw_mid.py.  GPIO19 stays in ALT4 (SPI1_MISO) so SPI1 TX is not
disrupted; backlight is driven HIGH via RPi.GPIO before opening SPI.
"""

import struct, time, logging
from PIL import Image

log = logging.getLogger(__name__)

try:
    import spidev
    import RPi.GPIO as GPIO
    _AVAIL = True
except ImportError:
    _AVAIL = False


class RawST7789:
    """240×240 ST7789 on SPI1 — pure spidev/RPi.GPIO, no gpiod."""

    def __init__(self, width, height, port, cs, dc, rst, backlight=None,
                 spi_speed_hz=40_000_000, rotation=0):
        self.w = width
        self.h = height
        self._dc  = dc
        self._rst = rst
        self._bl  = backlight

        if not _AVAIL:
            self._spi = None
            log.warning("spidev/RPi.GPIO not available — preview mode")
            return

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(dc, GPIO.OUT)

        # Backlight: drive HIGH if a pin is given.
        # GPIO19 = SPI1 MISO on this HAT — RPi.GPIO can drive it HIGH without
        # changing the SPI1 controller behaviour for TX (MOSI/SCLK unaffected).
        if backlight is not None:
            GPIO.setup(backlight, GPIO.OUT)
            GPIO.output(backlight, GPIO.HIGH)

        # Hardware reset
        GPIO.setup(rst, GPIO.OUT)
        GPIO.output(rst, GPIO.HIGH);  time.sleep(0.05)
        GPIO.output(rst, GPIO.LOW);   time.sleep(0.15)
        GPIO.output(rst, GPIO.HIGH);  time.sleep(0.20)

        self._spi = spidev.SpiDev()
        self._spi.open(port, cs)
        self._spi.max_speed_hz = spi_speed_hz
        self._spi.mode = 0

        self._init_display(rotation)
        log.info("RawST7789 %dx%d on SPI%d ready", width, height, port)

    # ── low-level helpers ────────────────────────────────────────────────────

    def _cmd(self, c):
        GPIO.output(self._dc, GPIO.LOW)
        self._spi.writebytes([c])

    def _data(self, d):
        GPIO.output(self._dc, GPIO.HIGH)
        self._spi.writebytes(list(d))

    def _init_display(self, rotation):
        self._cmd(0x01); time.sleep(0.15)   # SWRESET
        self._cmd(0x11); time.sleep(0.12)   # SLPOUT
        self._cmd(0x3A); self._data([0x55]) # COLMOD  16bpp RGB565
        self._cmd(0x36); self._data([0x00]) # MADCTL  normal
        self._cmd(0x21)                     # INVON   (required by most 240×240 panels)
        self._cmd(0x13)                     # NORON
        self._cmd(0x29); time.sleep(0.05)   # DISPON

    # ── public API ───────────────────────────────────────────────────────────

    def display(self, img: Image.Image):
        if self._spi is None:
            return
        if img.size != (self.w, self.h):
            img = img.resize((self.w, self.h), Image.LANCZOS)

        # Set window
        self._cmd(0x2A)
        self._data(struct.pack(">HH", 0, self.w - 1))   # CASET
        self._cmd(0x2B)
        self._data(struct.pack(">HH", 0, self.h - 1))   # RASET
        self._cmd(0x2C)                                   # RAMWR

        # Convert PIL RGB → RGB565 big-endian
        pixels = img.convert("RGB").tobytes()
        out = bytearray(self.w * self.h * 2)
        for i in range(self.w * self.h):
            r, g, b = pixels[i*3], pixels[i*3+1], pixels[i*3+2]
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            out[i*2]   = (rgb565 >> 8) & 0xFF
            out[i*2+1] = rgb565 & 0xFF

        GPIO.output(self._dc, GPIO.HIGH)
        CHUNK = 4096
        for off in range(0, len(out), CHUNK):
            self._spi.writebytes2(out[off:off+CHUNK])

    def cleanup(self):
        if self._spi:
            self._spi.close()
        GPIO.cleanup()
