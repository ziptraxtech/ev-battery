#!/usr/bin/env bash
# ZipSure EV Monitor — one-shot setup for Pi Zero 2W (Raspberry Pi OS Bookworm)
set -e

INSTALL_DIR="/home/pi/zipsure"
CONFIG_FILE="/home/pi/config.yaml"
SERVICE_FILE="/etc/systemd/system/dashboard.service"
BOOT_CONFIG="/boot/firmware/config.txt"   # Bookworm path (older: /boot/config.txt)

# Fall back to old path if needed
[ -f "$BOOT_CONFIG" ] || BOOT_CONFIG="/boot/config.txt"

echo "=== ZipSure Dashboard Setup ==="

# ── System packages ────────────────────────────────────────────────────────────
sudo apt-get update -qq
sudo apt-get install -y python3-pip python3-venv python3-dev \
    libjpeg-dev libopenjp2-7 fonts-roboto git

# ── SPI0 (Screens 1 & 2 — ST7735 0.96") ──────────────────────────────────────
sudo raspi-config nonint do_spi 0
echo "SPI0 enabled"

# ── SPI1 (Screen 0 — ST7789 1.3") ─────────────────────────────────────────────
if ! grep -q "dtoverlay=spi1-1cs" "$BOOT_CONFIG"; then
    echo "dtoverlay=spi1-1cs" | sudo tee -a "$BOOT_CONFIG"
    echo "SPI1 overlay added"
fi

# ── UART for SIM A7672S ────────────────────────────────────────────────────────
# Disable Bluetooth to free up the full UART (ttyAMA0) for the SIM module.
# The mini UART (/dev/ttyS0) is less stable at high baud rates.
if ! grep -q "dtoverlay=disable-bt" "$BOOT_CONFIG"; then
    echo "enable_uart=1"         | sudo tee -a "$BOOT_CONFIG"
    echo "dtoverlay=disable-bt"  | sudo tee -a "$BOOT_CONFIG"
    echo "UART enabled, Bluetooth UART disabled (SIM A7672S uses ttyAMA0)"
fi

# Disable serial console so UART is free for the SIM module
sudo raspi-config nonint do_serial_hw 0   # enable hardware serial
sudo raspi-config nonint do_serial_cons 1 # disable serial console

# ── Copy project files ────────────────────────────────────────────────────────
mkdir -p "$INSTALL_DIR"
cp -r .  "$INSTALL_DIR/"

# ── Python venv ───────────────────────────────────────────────────────────────
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
"$INSTALL_DIR/venv/bin/pip" install st7789 st7735 RPi.GPIO

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT_DIR="$INSTALL_DIR/display/fonts"
mkdir -p "$FONT_DIR"
FONT_BASE="https://github.com/googlefonts/RobotoMono/raw/main/fonts/ttf"
curl -sL "$FONT_BASE/RobotoMono-Bold.ttf"    -o "$FONT_DIR/RobotoMono-Bold.ttf"
curl -sL "$FONT_BASE/RobotoMono-Regular.ttf" -o "$FONT_DIR/RobotoMono-Regular.ttf"
echo "Fonts downloaded"

# ── Add pi user to dialout group (UART + USB serial access) ───────────────────
sudo usermod -aG dialout pi

# ── Systemd service ───────────────────────────────────────────────────────────
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=ZipSure EV Battery Dashboard
After=network.target
Wants=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python dashboard.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable dashboard.service
sudo systemctl start  dashboard.service

echo ""
echo "=== Setup complete — REBOOT REQUIRED ==="
echo "  The SPI1 overlay and UART changes take effect after reboot."
echo "  sudo reboot"
echo ""
echo "After reboot:"
echo "  Live logs : sudo journalctl -u dashboard -f"
echo "  Config    : $CONFIG_FILE"
echo "  SIM port  : /dev/ttyAMA0  (check with: ls /dev/tty*)"
echo "  ESP32 port: /dev/ttyUSB0  (check with: ls /dev/ttyUSB*)"
