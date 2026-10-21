"""Configuração de hardware por plataforma (macOS = desenvolvimento, Linux = Raspberry).

Tudo pode ser sobrescrito por variável de ambiente:
  BALANCA_PORT     porta serial da balança
  BALANCA_FORMATO  "7E1" (original do Mac) ou "8N1" (padrão no Linux)
  ESP32_BLE_ADDRESS / ESP32_BLE_NAME   alvo BLE do ESP32
"""
import os
import sys

EH_MAC = sys.platform == "darwin"

_FTDI_BY_ID = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A5069RR4-if00-port0"

if EH_MAC:
    _PORTA_PADRAO = "/dev/cu.usbserial-A5069RR4"
    _FORMATO_PADRAO = "7E1"
    _BLE_PADRAO = "46093007-6DC6-2835-640C-12A1EEE074F6"  # UUID do CoreBluetooth
else:
    # Nome fixo do adaptador FTDI (não muda com a porta USB); senão cai em ttyUSB0
    _PORTA_PADRAO = _FTDI_BY_ID if os.path.exists(_FTDI_BY_ID) else "/dev/ttyUSB0"
    # No Linux o kernel troca bytes com "erro de paridade" por 0x00, o que quebra os pacotes
    _FORMATO_PADRAO = "8N1"
    _BLE_PADRAO = ""  # no Linux é preciso o MAC do ESP32 (ESP32_BLE_ADDRESS) ou o nome

PORTA = os.environ.get("BALANCA_PORT", _PORTA_PADRAO)
FORMATO = os.environ.get("BALANCA_FORMATO", _FORMATO_PADRAO).upper()
BLE_ADDRESS = os.environ.get("ESP32_BLE_ADDRESS", _BLE_PADRAO)
BLE_NAME = os.environ.get("ESP32_BLE_NAME", "")


def cfg_serial(serial):
    """Parâmetros do pyserial conforme BALANCA_FORMATO."""
    if FORMATO == "7E1":
        return dict(bytesize=serial.SEVENBITS, parity=serial.PARITY_EVEN, stopbits=serial.STOPBITS_ONE)
    return dict(bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
