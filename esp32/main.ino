/*
 * ZipSure EV Battery Monitor — ESP32 Firmware
 *
 * Sensors:
 *   - MH-Z14A  NDIR CO2 sensor        (UART2: RX=GPIO16, TX=GPIO17)
 *   - PT100    RTD via MAX31865        (SPI:   CS=GPIO5, MISO=GPIO19, MOSI=GPIO23, SCLK=GPIO18)
 *   - WCM7500  Hall-effect current     (ADC:   GPIO34)
 *
 * Libraries required (install via Arduino Library Manager):
 *   - ArduinoJson       (Benoit Blanchon)
 *   - Adafruit MAX31865 (Adafruit)
 *
 * Output: newline-delimited JSON on USB Serial (115200 baud) every SEND_INTERVAL_MS
 *
 * JSON format:
 *   {"ts":12345,"gas_ppm":450,"temp_c":35.20,"current_a":12.50,
 *    "voltage_v":48.20,"power_w":600.1,"alerts":[]}
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Adafruit_MAX31865.h>
#include <SPI.h>

// ── Build-time options ────────────────────────────────────────────────────────
#define USE_MQTT          0       // 1 = enable WiFi + MQTT publish
#define SEND_INTERVAL_MS  2000   // sensor publish cadence (ms)

// ── MH-Z14A NDIR CO2 (UART2) ─────────────────────────────────────────────────
#define MHZ14A_RX_PIN     16
#define MHZ14A_TX_PIN     17
#define MHZ14A_BAUD       9600
#define MHZ14A_RANGE_PPM  5000   // 5000 ppm model (some are 2000 — check label)

// ── MAX31865 + PT100 (SPI) ────────────────────────────────────────────────────
#define MAX31865_CS_PIN   5
// MISO=19, MOSI=23, SCLK=18 are ESP32 default SPI — wired to the module directly
//
// MAX31865 board reference resistor:
//   Adafruit breakout: 430 Ω  (for PT100)  ← most common
//   If your board uses a 4300 Ω resistor, change RREF to 4300.0
#define RREF              430.0
#define RNOMINAL          100.0  // PT100 = 100 Ω at 0 °C

// ── WCM7500 Hall-effect current sensor (ADC) ──────────────────────────────────
// WCM7500 is a unidirectional Hall-effect sensor:
//   Supply 5 V (via ESP32 5V pin)
//   Vout at 0 A ≈ 0.5 V   (maps to ~620 ADC counts on 3.3 V ESP32 ADC)
//   Sensitivity: CHECK YOUR DATASHEET — typical values are 40–66 mV/A
//   ⚠ Adjust WCM7500_SENSITIVITY to match the exact variant you have.
//   Common variants: 50 A (40 mV/A), 100 A (21 mV/A)
#define WCM7500_PIN          34
#define WCM7500_SENSITIVITY  40.0   // mV per Amp — VERIFY from datasheet
#define WCM7500_VOUT_ZERO    500.0  // mV output at 0 A (0.5 V for 5 V supply)
#define ADC_VREF_MV          3300
#define ADC_MAX              4095

// Battery voltage divider (GPIO35, optional — set -1 to disable)
// R1=47 kΩ, R2=10 kΩ → 0–60 V maps to 0–3.3 V
#define VOLTAGE_PIN          35
#define VOLTAGE_R1           47000.0
#define VOLTAGE_R2           10000.0

// ── Alert thresholds ──────────────────────────────────────────────────────────
#define GAS_WARN_PPM         1000
#define GAS_CRIT_PPM         2000
#define TEMP_WARN_C          45.0
#define TEMP_CRIT_C          60.0

// ── MQTT (only compiled when USE_MQTT=1) ──────────────────────────────────────
#if USE_MQTT
  #include <WiFi.h>
  #include <PubSubClient.h>
  const char* WIFI_SSID   = "YOUR_WIFI_SSID";
  const char* WIFI_PASS   = "YOUR_WIFI_PASSWORD";
  const char* MQTT_BROKER = "192.168.1.100";
  const int   MQTT_PORT   = 1883;
  const char* MQTT_TOPIC  = "zipsure/battery/sensors";
  const char* MQTT_CLIENT = "esp32-battery-001";
  WiFiClient    wifiClient;
  PubSubClient  mqttClient(wifiClient);
#endif

// ── Objects ───────────────────────────────────────────────────────────────────
HardwareSerial mhzSerial(2);  // UART2
Adafruit_MAX31865 rtd = Adafruit_MAX31865(MAX31865_CS_PIN);

unsigned long lastSendMs = 0;

// MH-Z14A read command (identical to MH-Z19B UART protocol)
const uint8_t MHZ_READ_CMD[9] = {0xFF,0x01,0x86,0x00,0x00,0x00,0x00,0x00,0x79};

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  // MH-Z14A
  mhzSerial.begin(MHZ14A_BAUD, SERIAL_8N1, MHZ14A_RX_PIN, MHZ14A_TX_PIN);

  // MAX31865 — 2-wire PT100 (change to MAX31865_3WIRE or MAX31865_4WIRE if needed)
  rtd.begin(MAX31865_2WIRE);

  // ADC
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);  // 0–3.3 V range

  #if USE_MQTT
    connectWifi();
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  #endif

  Serial.println("{\"status\":\"boot\"}");
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
  #if USE_MQTT
    if (!mqttClient.connected()) reconnectMqtt();
    mqttClient.loop();
  #endif

  if (millis() - lastSendMs >= SEND_INTERVAL_MS) {
    lastSendMs = millis();
    publishReadings();
  }
}

// ── Sensor reads ──────────────────────────────────────────────────────────────

// MH-Z14A — returns CO2 in ppm, or -1 on read failure
int readGasPpm() {
  while (mhzSerial.available()) mhzSerial.read();  // flush

  mhzSerial.write(MHZ_READ_CMD, 9);
  delay(100);

  if (mhzSerial.available() < 9) return -1;

  uint8_t buf[9];
  mhzSerial.readBytes(buf, 9);

  if (buf[0] != 0xFF || buf[1] != 0x86) return -1;

  // Verify checksum
  uint8_t cs = 0;
  for (int i = 1; i < 8; i++) cs += buf[i];
  cs = (~cs) + 1;
  if (cs != buf[8]) return -1;

  return (buf[2] << 8) | buf[3];
}

// MAX31865 + PT100 — returns °C, or -999 on fault
float readTemperatureC() {
  uint8_t fault = rtd.readFault();
  if (fault) {
    rtd.clearFault();
    return -999.0;
  }
  return rtd.temperature(RNOMINAL, RREF);
}

// WCM7500 — returns current in Amps
float readCurrentA() {
  // Average 64 samples for ADC noise reduction
  long sum = 0;
  for (int i = 0; i < 64; i++) {
    sum += analogRead(WCM7500_PIN);
    delayMicroseconds(100);
  }
  float adcVal   = sum / 64.0;
  float vout_mv  = (adcVal / ADC_MAX) * ADC_VREF_MV;
  float current  = (vout_mv - WCM7500_VOUT_ZERO) / WCM7500_SENSITIVITY;
  return current < 0 ? 0 : current;  // WCM7500 is unidirectional
}

// Optional battery pack voltage
float readVoltageV() {
  #if VOLTAGE_PIN < 0
    return -1.0;
  #endif
  float adc_v = (analogRead(VOLTAGE_PIN) / (float)ADC_MAX) * (ADC_VREF_MV / 1000.0);
  return adc_v * ((VOLTAGE_R1 + VOLTAGE_R2) / VOLTAGE_R2);
}

// ── Publish ───────────────────────────────────────────────────────────────────
void publishReadings() {
  int   gas_ppm = readGasPpm();
  float temp_c  = readTemperatureC();
  float current = readCurrentA();
  float voltage = readVoltageV();
  float power   = (voltage > 0 && current >= 0) ? voltage * current : -1.0;

  StaticJsonDocument<256> doc;
  doc["ts"]        = millis() / 1000;
  doc["gas_ppm"]   = gas_ppm;
  doc["temp_c"]    = serialized(String(temp_c, 2));
  doc["current_a"] = serialized(String(current, 2));
  doc["voltage_v"] = serialized(String(voltage, 2));
  doc["power_w"]   = serialized(String(power, 1));

  JsonArray alerts = doc.createNestedArray("alerts");
  if (gas_ppm  >= GAS_CRIT_PPM)  alerts.add("GAS_CRITICAL");
  else if (gas_ppm >= GAS_WARN_PPM)  alerts.add("GAS_WARNING");
  if (temp_c   >= TEMP_CRIT_C)   alerts.add("TEMP_CRITICAL");
  else if (temp_c >= TEMP_WARN_C) alerts.add("TEMP_WARNING");

  String json;
  serializeJson(doc, json);

  Serial.println(json);  // Pi reads this

  #if USE_MQTT
    mqttClient.publish(MQTT_TOPIC, json.c_str());
  #endif
}

// ── WiFi / MQTT helpers ───────────────────────────────────────────────────────
#if USE_MQTT
void connectWifi() {
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    retries++;
  }
}

void reconnectMqtt() {
  int retries = 0;
  while (!mqttClient.connected() && retries < 5) {
    mqttClient.connect(MQTT_CLIENT);
    delay(1000);
    retries++;
  }
}
#endif
