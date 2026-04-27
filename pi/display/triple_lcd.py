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

Install driver: pip install st7789 st7735 RPi.GPIO
"""

import logging
from PIL import Image

log = logging.getLogger(__name__)

try:
    import st7789
    import st7735
    _BACKEND = "pimoroni"
except ImportError:
    _BACKEND = None
    log.warning("Display libraries not found — running in preview (PNG) mode")


class Screen:

    def __init__(self, cfg: dict):
        self.id    = cfg["id"]
        self.label = cfg["label"]
        self.w     = cfg["width"]
        self.h     = cfg["height"]
        self._dev  = None

        if _BACKEND != "pimoroni":
            return

        try:
            spi_port = cfg["spi_port"]
            # Check SPI device exists before attempting init
            import os
            spi_dev = f"/dev/spidev{spi_port}.0"
            if not os.path.exists(spi_dev):
                log.error("Screen %d: %s not found — is dtoverlay=spi%d-1cs in /boot/firmware/config.txt?",
                          self.id, spi_dev, spi_port)
                return

            kwargs = dict(
                width=self.w,
                height=self.h,
                rotation=cfg.get("rotation", 0),
                port=spi_port,
                cs=cfg["cs"],       # CE index: 0=CE0, 1=CE1 (NOT the GPIO pin)
                dc=cfg["dc_pin"],
                rst=cfg.get("rst_pin"),
                backlight=cfg.get("backlight_pin"),
                spi_speed_hz=40_000_000,
            )
            driver = cfg.get("driver", "ST7789").upper()
            if driver == "ST7789":
                # Pre-drive RST HIGH so display is out of hardware reset before init.
                # A previous process exit can leave RST LOW via gpiod cleanup.
                rst_pin = cfg.get("rst_pin")
                if rst_pin:
                    import subprocess as _sp, time as _t
                    _sp.run(["pinctrl", "set", str(rst_pin), "op", "dh"],
                            check=False, capture_output=True)
                    _t.sleep(0.1)
                self._dev = st7789.ST7789(**kwargs)
            else:
                # ST7735 for the two 0.96" screens — pass offset + bgr if set
                if cfg.get("offset_left") is not None:
                    kwargs["offset_left"] = cfg["offset_left"]
                if cfg.get("offset_top") is not None:
                    kwargs["offset_top"] = cfg["offset_top"]
                if cfg.get("bgr") is not None:
                    kwargs["bgr"] = cfg["bgr"]
                self._dev = st7735.ST7735(**kwargs)
            log.info("Screen %d (%s) %dx%d on SPI%d ready",
                     self.id, self.label, self.w, self.h, cfg["spi_port"])
        except Exception as e:
            import traceback
            log.error("Screen %d init failed: %s\n%s", self.id, e, traceback.format_exc())

    def show(self, img: Image.Image):
        # Resize to exact screen dimensions if caller passes wrong size
        if img.size != (self.w, self.h):
            img = img.resize((self.w, self.h), Image.LANCZOS)

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
