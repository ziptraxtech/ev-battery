"""
SIM A7672S 4G LTE uploader — AT command HTTP POST over UART.

The SIM A7672S supports HTTP/HTTPS via its built-in TCP stack using AT commands.
This is the preferred transport for the vehicle — no WiFi dependency.

UART wiring (Pi Zero 2W):
  Pi GPIO14 (TXD, board pin 8)  → A7672S RXD
  Pi GPIO15 (RXD, board pin 10) → A7672S TXD
  GND                           → A7672S GND

Required in /boot/config.txt:
  enable_uart=1
  dtoverlay=disable-bt          (frees up ttyAMA0 — full UART, more stable)

Serial port will then be /dev/ttyAMA0 or /dev/serial0
"""

import json
import logging
import threading
import time
from collections import deque

import serial

log = logging.getLogger(__name__)

_OK        = b"OK"
_ERROR     = b"ERROR"
_DOWNLOAD  = b"DOWNLOAD"
_CONNECT   = b"CONNECT"


class GsmUploader:

    def __init__(self, cfg: dict, device_cfg: dict):
        self._cfg        = cfg["gsm"]
        self._device_id  = device_cfg.get("id", "pizero-001")
        self._vehicle_id = device_cfg.get("vehicle_id", "EV-001")
        self._endpoint   = self._cfg["endpoint"]
        self._api_key    = self._cfg.get("api_key", "")
        self._apn        = self._cfg.get("apn", "")
        self._interval   = self._cfg.get("interval_seconds", 10)
        self._at_timeout = self._cfg.get("at_timeout", 10)
        self._queue: deque = deque(maxlen=500)
        self._running    = False
        self._thread     = None
        self._ser        = None
        self._ready      = False

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()

    def enqueue(self, reading: dict):
        enriched = {
            **reading,
            "device_id":  self._device_id,
            "vehicle_id": self._vehicle_id,
        }
        self._queue.append(enriched)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def _run(self):
        while self._running:
            try:
                self._ser = serial.Serial(
                    self._cfg["port"],
                    self._cfg.get("baud", 115200),
                    timeout=self._at_timeout,
                )
                log.info("GSM UART open: %s", self._cfg["port"])
                self._init_modem()

                while self._running:
                    time.sleep(self._interval)
                    if not self._queue:
                        continue
                    batch = []
                    while self._queue:
                        batch.append(self._queue.popleft())
                    self._upload_batch(batch)

            except serial.SerialException as e:
                log.warning("GSM serial error: %s — retry in 5s", e)
                time.sleep(5)
            except Exception as e:
                log.error("GSM uploader error: %s", e)
                time.sleep(5)
            finally:
                if self._ser and self._ser.is_open:
                    self._ser.close()

    # ── Modem init ────────────────────────────────────────────────────────────

    def _init_modem(self):
        self._at("AT")                        # sanity check
        self._at("ATE0")                      # echo off
        self._at("AT+CMEE=2")                 # verbose errors

        # Wait for SIM and network registration (up to 30s)
        for _ in range(10):
            resp = self._at("AT+CREG?", expect="+CREG")
            if resp and (",1" in resp or ",5" in resp):
                break
            time.sleep(3)

        # Set APN and activate PDP context
        self._at(f'AT+CGDCONT=1,"IP","{self._apn}"')
        self._at("AT+CGACT=1,1", timeout=20)

        self._ready = True
        log.info("GSM modem ready, network registered")

    # ── HTTP POST ─────────────────────────────────────────────────────────────

    def _upload_batch(self, batch: list):
        if not self._ready:
            log.warning("GSM not ready — re-queuing %d readings", len(batch))
            self._queue.extendleft(reversed(batch))
            return

        payload = json.dumps({"readings": batch})
        payload_bytes = payload.encode()
        length = len(payload_bytes)

        # Parse host and path from endpoint URL
        url = self._endpoint
        if "://" in url:
            url = url.split("://", 1)[1]
        host, _, path = url.partition("/")
        path = "/" + path if path else "/"
        use_https = self._endpoint.startswith("https")
        port = 443 if use_https else 80

        try:
            # Terminate any existing HTTP session
            self._at("AT+HTTPTERM", check=False)
            time.sleep(0.2)

            self._at("AT+HTTPINIT")
            self._at(f'AT+HTTPPARA="CID",1')
            self._at(f'AT+HTTPPARA="URL","{self._endpoint}"')
            self._at(f'AT+HTTPPARA="CONTENT","application/json"')
            self._at(f'AT+HTTPPARA="USERDATA","X-API-Key: {self._api_key}\\r\\n"')

            # Send data
            resp = self._at(f"AT+HTTPDATA={length},5000", expect="DOWNLOAD", timeout=6)
            if resp is None:
                raise RuntimeError("HTTPDATA no DOWNLOAD prompt")
            self._ser.write(payload_bytes)
            time.sleep(0.5)

            # Execute POST
            action_resp = self._at("AT+HTTPACTION=1", expect="+HTTPACTION", timeout=30)
            if action_resp is None:
                raise RuntimeError("HTTPACTION timeout")

            # Check HTTP status code (format: +HTTPACTION: 1,<status>,<len>)
            parts = action_resp.strip().split(",")
            if len(parts) >= 2:
                status_code = int(parts[1])
                if status_code == 200 or status_code == 201:
                    log.info("GSM upload OK — %d readings, HTTP %d", len(batch), status_code)
                else:
                    log.warning("GSM upload HTTP %d", status_code)

        except Exception as e:
            log.error("GSM HTTP POST failed: %s — re-queuing", e)
            self._queue.extendleft(reversed(batch))
        finally:
            self._at("AT+HTTPTERM", check=False)

    # ── AT command helper ─────────────────────────────────────────────────────

    def _at(self, cmd: str, expect: str = None, timeout: int = None,
            check: bool = True) -> str | None:
        if not self._ser or not self._ser.is_open:
            return None

        t = timeout or self._at_timeout
        self._ser.write((cmd + "\r\n").encode())
        self._ser.flush()

        deadline = time.monotonic() + t
        lines = []
        while time.monotonic() < deadline:
            raw = self._ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            lines.append(line)
            log.debug("AT << %s", line)

            if expect and expect in line:
                return line
            if line == "OK":
                return line
            if "ERROR" in line:
                if check:
                    log.warning("AT error for [%s]: %s", cmd, line)
                return None

        log.warning("AT timeout for [%s]", cmd)
        return None
