#!/bin/bash
# Inicialização no Raspberry Pi (substitui iniciar.command do macOS)
cd "$(dirname "$0")"

echo "--- [SISTEMA] Iniciando Ambiente IoT ---"

echo "--- [DOCKER] Subindo containers..."
docker compose up -d || exit 1

# Ambiente virtual Python (criado na primeira execução)
if [ ! -d venv ]; then
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi

# Configurações do hardware (ajuste conforme o seu Raspberry)
# BALANCA_PORT é detectada sozinha (FTDI em /dev/serial/by-id); defina só se precisar trocar
# export BALANCA_PORT=/dev/ttyUSB0
export CAMERA_INDEX="${CAMERA_INDEX:-0}"
# export ESP32_BLE_ADDRESS="AA:BB:CC:DD:EE:FF"   # MAC do ESP32
# export ESP32_BLE_NAME="NOME_DO_ESP32"          # alternativa ao MAC

sleep 5
./venv/bin/python app.py
