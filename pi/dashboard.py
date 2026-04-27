#!/usr/bin/env python3
"""
ZipSure EV Battery Monitor — Pi Zero 2W Dashboard
Reads sensor data from ESP32, renders to Triple LCD HAT, uploads to cloud.
"""

import logging
import signal
import sys
import time
import threading
import yaml

from display.triple_lcd import TripleLCD
from display.widgets    import gas_screen, temperature_screen, current_screen, offline_screen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dashboard")

# ── Config ────────────────────────────────────────────────────────────────────

def load_config(path: str = "../config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

# ── Alert level helpers ───────────────────────────────────────────────────────

def gas_level(ppm, thresholds) -> str:
    if ppm is None or ppm < 0:      return "ok"
    if ppm >= thresholds["gas_ppm_critical"]: return "critical"
    if ppm >= thresholds["gas_ppm_warning"]:  return "warning"
    return "ok"

def temp_level(temp_c, thresholds) -> str:
    if temp_c is None or temp_c < -900: return "ok"
    if temp_c >= thresholds["temp_critical_c"]: return "critical"
    if temp_c >= thresholds["temp_warning_c"]:  return "warning"
    return "ok"

# ── Dashboard ─────────────────────────────────────────────────────────────────

class Dashboard:

    def __init__(self, cfg: dict):
        self._cfg        = cfg
        self._thresholds = cfg["alerts"]
        self._latest     = None
        self._last_rx    = 0.0
        self._lock       = threading.Lock()
        self._running    = False

        self._display  = TripleLCD(cfg)

        cloud_mode = cfg["cloud"].get("mode", "http")
        if cloud_mode == "gsm":
            from cloud.gsm_uploader import GsmUploader
            self._uploader = GsmUploader(cfg["cloud"], cfg["device"])
        else:
            from cloud.uploader import CloudUploader
            self._uploader = CloudUploader(cfg["cloud"], cfg["device"])

        comms = cfg["comms"]
        if comms["mode"] == "serial":
            from sensors.serial_reader import SerialReader
            sc = comms["serial"]
            self._reader = SerialReader(
                port=sc["port"], baud=sc["baud"],
                timeout=sc["timeout"], callback=self._on_data
            )
        else:
            from sensors.mqtt_reader import MqttReader
            self._reader = MqttReader(comms["mqtt"], callback=self._on_data)

    def _on_data(self, data: dict):
        with self._lock:
            self._latest  = data
            self._last_rx = time.monotonic()
        self._uploader.enqueue(data)
        log.debug("RX: gas=%s ppm  temp=%s°C  current=%s A",
                  data.get("gas_ppm"), data.get("temp_c"), data.get("current_a"))
        if data.get("alerts"):
            log.warning("ALERTS: %s", data["alerts"])

    def start(self):
        self._running = True
        self._reader.start()
        self._uploader.start()
        log.info("Dashboard started — comms mode: %s", self._cfg["comms"]["mode"])
        self._render_loop()

    def stop(self):
        self._running = False
        self._reader.stop()
        self._uploader.stop()
        self._display.blank_all()
        log.info("Dashboard stopped")

    def _render_loop(self):
        fps_interval = 1.0  # refresh display every second
        while self._running:
            t0 = time.monotonic()

            with self._lock:
                data    = self._latest
                last_rx = self._last_rx

            stale = (time.monotonic() - last_rx) > 10.0  # 10s timeout = offline

            if stale or data is None:
                images = [
                    offline_screen("CO₂ / GAS", (240, 240)),
                    offline_screen("GAS + TEMP", (160, 80)),
                    offline_screen("AMP + VOLT", (160, 80)),
                ]
            else:
                gas_ppm   = data.get("gas_ppm")
                temp_c    = data.get("temp_c")
                current_a = data.get("current_a")
                voltage_v = data.get("voltage_v")
                power_w   = data.get("power_w")

                t_lvl = temp_level(temp_c, self._thresholds)
                g_lvl = gas_level(gas_ppm, self._thresholds)
                images = [
                    gas_screen(gas_ppm, g_lvl,
                               temp_c=temp_c, temp_status=t_lvl,
                               current_a=current_a, voltage_v=voltage_v),
                    temperature_screen(temp_c, t_lvl,
                                       gas_ppm=gas_ppm, gas_status=g_lvl),
                    current_screen(current_a, voltage_v, power_w,
                                   self._thresholds["current_max_a"]),
                ]

            self._display.show_all(images)

            elapsed = time.monotonic() - t0
            sleep_for = max(0.0, fps_interval - elapsed)
            time.sleep(sleep_for)

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    cfg = load_config()
    dash = Dashboard(cfg)

    def _shutdown(sig, frame):
        log.info("Shutdown signal received")
        dash.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    dash.start()

if __name__ == "__main__":
    main()
