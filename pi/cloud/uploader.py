"""
Cloud uploader — batches sensor readings and POSTs to your server every N seconds.
Also supports MQTT publish as an alternative transport.
"""

import json
import logging
import threading
import time
from collections import deque

import requests

log = logging.getLogger(__name__)


class CloudUploader:

    def __init__(self, cfg: dict, device_cfg: dict):
        self._cfg        = cfg
        self._device_id  = device_cfg.get("id", "pizero-001")
        self._vehicle_id = device_cfg.get("vehicle_id", "EV-001")
        self._queue: deque = deque(maxlen=500)  # buffer if server unreachable
        self._running    = False
        self._thread     = None
        self._interval   = cfg.get("http", {}).get("interval_seconds", 10)
        self._mode       = cfg.get("mode", "http")

        if self._mode == "mqtt":
            self._setup_mqtt()

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def enqueue(self, reading: dict):
        """Called from the sensor reader thread whenever new data arrives."""
        enriched = {
            **reading,
            "device_id":  self._device_id,
            "vehicle_id": self._vehicle_id,
        }
        self._queue.append(enriched)

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def _run(self):
        while self._running:
            time.sleep(self._interval)
            if not self._queue:
                continue
            # Drain the queue into one batch
            batch = []
            while self._queue:
                batch.append(self._queue.popleft())

            if self._mode == "http":
                self._post_batch(batch)
            elif self._mode == "mqtt":
                for item in batch:
                    self._mqtt_publish(item)

    def _post_batch(self, batch: list):
        http_cfg = self._cfg.get("http", {})
        url      = http_cfg.get("endpoint", "")
        api_key  = http_cfg.get("api_key", "")
        timeout  = http_cfg.get("timeout", 5)

        if not url or url.startswith("https://your-server"):
            return  # not configured yet

        headers = {"Content-Type": "application/json", "X-API-Key": api_key}
        payload = {"readings": batch}

        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                log.debug("Uploaded %d readings", len(batch))
            else:
                log.warning("Upload failed %d: %s", r.status_code, r.text[:200])
                # Put back into queue for retry
                self._queue.extendleft(reversed(batch))
        except requests.RequestException as e:
            log.warning("Upload error: %s", e)
            self._queue.extendleft(reversed(batch))

    # ── MQTT ──────────────────────────────────────────────────────────────────

    def _setup_mqtt(self):
        try:
            import paho.mqtt.client as mqtt
            mqtt_cfg = self._cfg.get("mqtt", {})
            self._mqtt_client = mqtt.Client(client_id=f"uploader-{self._device_id}")
            if mqtt_cfg.get("username"):
                self._mqtt_client.username_pw_set(
                    mqtt_cfg["username"], mqtt_cfg.get("password", "")
                )
            if mqtt_cfg.get("tls"):
                self._mqtt_client.tls_set()
            self._mqtt_client.connect(
                mqtt_cfg["broker"], mqtt_cfg.get("port", 8883), keepalive=60
            )
            self._mqtt_client.loop_start()
            self._mqtt_topic_tpl = mqtt_cfg.get(
                "topic", "zipsure/fleet/{device_id}/telemetry"
            )
        except Exception as e:
            log.error("MQTT uploader setup failed: %s", e)
            self._mqtt_client = None

    def _mqtt_publish(self, item: dict):
        if not hasattr(self, "_mqtt_client") or not self._mqtt_client:
            return
        topic = self._mqtt_topic_tpl.format(device_id=self._device_id)
        self._mqtt_client.publish(topic, json.dumps(item), qos=1)
