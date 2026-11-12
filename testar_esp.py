"""Testa a conexão BLE com o ESP32 (sem Flask, sem banco).

Conecta, escuta as notificações, envia o comando "M" (medir altura, o mesmo do botão
da interface) e mostra o que o ESP32 responde.

Uso: python testar_esp.py [segundos] [--sem-medir]
  segundos      quanto tempo esperar pela resposta (padrão 15)
  --sem-medir   só conecta e escuta, sem enviar "M"
"""
import argparse
import asyncio
import struct
import sys

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("bleak não instalado: pip install bleak")
    sys.exit(1)

import config_hw

UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  # PC -> ESP32
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # ESP32 -> PC


def ao_receber(_, data):
    print(f"  recebido ({len(data)} bytes): {data.hex(' ')}")
    if len(data) == 20:
        msg = struct.unpack("<H9H", data)
        print(f"  -> medida principal: {msg[0] / 100.0:.2f} | amostras: {list(msg[1:])}")


async def main(segundos, medir):
    alvo = config_hw.BLE_ADDRESS
    print(f"Procurando o ESP32 ({alvo or config_hw.BLE_NAME})...")
    if alvo:
        dispositivo = await BleakScanner.find_device_by_address(alvo, timeout=15.0)
    else:
        dispositivo = await BleakScanner.find_device_by_name(config_hw.BLE_NAME, timeout=15.0)
    if dispositivo is None:
        print("ESP32 não encontrado. Ele está ligado e perto? Rode listar_bluetooth.py para conferir.")
        sys.exit(1)
    print(f"Encontrado: {dispositivo.name} [{dispositivo.address}]. Conectando...")

    async with BleakClient(dispositivo) as client:
        print("CONECTADO!")
        await client.start_notify(UART_TX_CHAR_UUID, ao_receber)
        print("Escutando notificações.")
        if medir:
            print('Enviando comando "M" (medir)...')
            await client.write_gatt_char(UART_RX_CHAR_UUID, b"M")
        await asyncio.sleep(segundos)
        await client.stop_notify(UART_TX_CHAR_UUID)
    print("Desconectado. Teste concluído.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("segundos", nargs="?", type=float, default=15.0)
    ap.add_argument("--sem-medir", action="store_true")
    args = ap.parse_args()
    try:
        asyncio.run(main(args.segundos, not args.sem_medir))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Erro: {e}")
        sys.exit(1)
