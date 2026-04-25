import json
import threading
import time
import serial
import logging

log = logging.getLogger(__name__)


class SerialReader:
    """Reads JSON sensor frames from ESP32 over USB UART."""

    def __init__(self, port: str, baud: int, timeout: float, callback):
        self._port = port
        self._baud = baud
        self._timeout = timeout
        self._callback = callback
        self._running = False
        self._thread = None
        self._ser = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._ser:
            self._ser.close()

    def _run(self):
        while self._running:
            try:
                self._ser = serial.Serial(
                    self._port, self._baud, timeout=self._timeout
                )
                log.info("Serial connected: %s @ %d baud", self._port, self._baud)
                while self._running:
                    raw = self._ser.readline().decode("utf-8", errors="ignore").strip()
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                        if "gas_ppm" in data:  # valid sensor frame
                            self._callback(data)
                    except json.JSONDecodeError:
                        log.debug("Non-JSON line: %s", raw)
            except serial.SerialException as e:
                log.warning("Serial error: %s — retrying in 3s", e)
                time.sleep(3)
            finally:
                if self._ser and self._ser.is_open:
                    self._ser.close()
