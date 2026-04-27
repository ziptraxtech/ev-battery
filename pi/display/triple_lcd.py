"""
Waveshare Zero LCD HAT (A) driver — 3 independent screens.

Screen layout on the HAT:
  Screen 0 — 1.3"  240×240  ST7789  SPI1  (large, top)
  Screen 1 — 0.96" 160×80   ST7735  SPI0 CE0
  Screen 2 — 0.96" 160×80   ST7735  SPI0 CE1

/boot/config.txt requirements:
  dtoverlay=spi1-1cs          (enables SPI1)
  enable_uart=1               (for SIM A7672S)
  dtoverlay=disable-bt        (frees full UART for SIM module)

Install driver: pip install st7735 spidev RPi.GPIO
"""

import logging
from PIL import Image

log = logging.getLogger(__name__)

# ST7789 uses our raw spidev/RPi.GPIO driver (avoids gpiod/SPI1 MISO conflict)
try:
    from .raw_st7789 import RawST7789
    _ST7789_AVAIL = True
except ImportError:
    _ST7789_AVAIL = False
    log.warning("raw_st7789 unavailable — ST7789 screen will be skipped")

try:
    import st7735
    _ST7735_AVAIL = True
except ImportError:
    _ST7735_AVAIL = False
    log.warning("st7735 not found — ST7735 screens will be skipped")


class Screen:

    def __init__(self, cfg: dict):
        self.id    = cfg["id"]
        self.label = cfg["label"]
        self.w     = cfg["width"]
        self.h     = cfg["height"]
        self._dev  = None
        self._landscape_rot = 0

        driver = cfg.get("driver", "ST7789").upper()

        try:
            import os
            spi_port = cfg["spi_port"]
            spi_dev = f"/dev/spidev{spi_port}.0"
            if not os.path.exists(spi_dev):
                log.error("Screen %d: %s not found", self.id, spi_dev)
                return

            if driver == "ST7789":
                if not _ST7789_AVAIL:
                    return
                self._dev = RawST7789(
                    width=self.w,
                    height=self.h,
                    port=spi_port,
                    cs=cfg["cs"],
                    dc=cfg["dc_pin"],
                    rst=cfg["rst_pin"],
                    backlight=cfg.get("backlight_pin"),
                    spi_speed_hz=cfg.get("spi_speed", 40_000_000),
                    rotation=cfg.get("rotation", 0),
                )
            else:
                if not _ST7735_AVAIL:
                    return
                # ST7735 on this HAT is a 160×80 landscape panel whose controller
                # is natively 80×160 portrait (132×162 GDDRAM, MV bit rotates it).
                # Passing width=160, height=80 to the library causes RASET to cover
                # only 80 rows instead of 160, filling just the left half.
                # Fix: pass portrait dims (w↔h swapped) so RASET = 1..160 correctly,
                # then rotate each incoming landscape image to portrait before display.
                rot = cfg.get("rotation", 0)
                landscape = (rot in (1, 3)) and self.w > self.h
                hw_w = self.h if landscape else self.w
                hw_h = self.w if landscape else self.h
                self._landscape_rot = rot if landscape else 0

                kwargs = dict(
                    width=hw_w,
                    height=hw_h,
                    rotation=rot,
                    port=spi_port,
                    cs=cfg["cs"],
                    dc=cfg["dc_pin"],
                    rst=cfg.get("rst_pin"),
                    backlight=cfg.get("backlight_pin"),
                    spi_speed_hz=40_000_000,
                )
                if cfg.get("offset_left") is not None:
                    kwargs["offset_left"] = cfg["offset_left"]
                if cfg.get("offset_top") is not None:
                    kwargs["offset_top"] = cfg["offset_top"]
                if cfg.get("bgr") is not None:
                    kwargs["bgr"] = cfg["bgr"]
                self._dev = st7735.ST7735(**kwargs)

            log.info("Screen %d (%s) %dx%d on SPI%d ready",
                     self.id, self.label, self.w, self.h, spi_port)
        except Exception as e:
            log.error("Screen %d init failed: %s", self.id, e)
            import gc; gc.collect()

    def show(self, img: Image.Image):
        if img.size != (self.w, self.h):
            img = img.resize((self.w, self.h), Image.LANCZOS)

        # Rotate landscape image to portrait for the hardware driver
        if self._landscape_rot:
            img = img.rotate(180, expand=True)

        if self._dev:
            self._dev.display(img)
        else:
            path = f"/tmp/zipsure_screen_{self.id}_{self.label.lower()}.png"
            img.save(path)


class TripleLCD:

    def __init__(self, cfg: dict):
        self._screens = [Screen(s) for s in cfg["display"]["screens"]]

    def show_all(self, images: list):
        for screen, img in zip(self._screens, images):
            try:
                screen.show(img)
            except Exception as e:
                log.error("Screen %d render error: %s", screen.id, e)

    def blank_all(self):
        for screen in self._screens:
            try:
                screen.show(Image.new("RGB", (screen.w, screen.h), (0, 0, 0)))
            except Exception:
                pass

    @property
    def screens(self):
        return self._screens
