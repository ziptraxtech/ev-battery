import json
import logging
import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)


class MqttReader:
    """Subscribes to ESP32 sensor topic via MQTT broker."""

    def __init__(self, cfg: dict, callback):
        self._cfg = cfg
        self._callback = callback
        self._client = mqtt.Client(client_id=cfg.get("client_id", "pizero"))

        if cfg.get("username"):
            self._client.username_pw_set(cfg["username"], cfg.get("password", ""))
        if cfg.get("tls"):
            self._client.tls_set()

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def start(self):
        self._client.connect(
            self._cfg["broker"],
            self._cfg.get("port", 1883),
            keepalive=60,
        )
        self._client.loop_start()

    def stop(self):
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(self._cfg["topic"])
            log.info("MQTT subscribed: %s", self._cfg["topic"])
        else:
            log.error("MQTT connect failed, rc=%d", rc)

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            if "gas_ppm" in data:
                self._callback(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            log.debug("Bad MQTT payload: %s", e)
