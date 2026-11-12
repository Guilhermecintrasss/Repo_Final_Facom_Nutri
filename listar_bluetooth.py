"""Lista os dispositivos Bluetooth (BLE) próximos, para descobrir o endereço do ESP32.

Uso: python listar_bluetooth.py [segundos] [--filtro TEXTO]
  segundos        duração do scan (padrão 10)
  --filtro TEXTO  mostra só dispositivos cujo nome contém TEXTO

Os dispositivos que anunciam o serviço UART Nordic (usado pelo ESP32 deste projeto)
aparecem marcados com <<< PROVÁVEL ESP32 >>>.
No Linux o "endereço" é o MAC (AA:BB:CC:DD:EE:FF); no macOS é um UUID gerado pelo sistema.
"""
import argparse
import asyncio
import sys

try:
    from bleak import BleakScanner
except ImportError:
    print("bleak não instalado: pip install bleak")
    sys.exit(1)

UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"


async def main(segundos, filtro):
    print(f"Escaneando BLE por {segundos:.0f}s... (ligue/reinicie o ESP32 agora)\n")
    encontrados = await BleakScanner.discover(timeout=segundos, return_adv=True)

    linhas = []
    for dispositivo, adv in encontrados.values():
        nome = adv.local_name or dispositivo.name or "(sem nome)"
        if filtro and filtro.lower() not in nome.lower():
            continue
        uuids = [u.lower() for u in (adv.service_uuids or [])]
        linhas.append((adv.rssi, nome, dispositivo.address, uuids))

    if not linhas:
        print("Nenhum dispositivo encontrado. Confira se o Bluetooth está ligado e o ESP32 alimentado.")
        return

    # Mais forte (mais perto) primeiro
    linhas.sort(key=lambda l: l[0], reverse=True)
    for rssi, nome, endereco, uuids in linhas:
        marca = "   <<< PROVÁVEL ESP32 >>>" if UART_SERVICE_UUID in uuids else ""
        print(f"Nome:      {nome}{marca}")
        print(f"Endereço:  {endereco}")
        print(f"Sinal:     {rssi} dBm")
        if uuids:
            print(f"Serviços:  {', '.join(uuids)}")
        print("-" * 60)
    print(f"\n{len(linhas)} dispositivo(s). Copie o Nome e o Endereço do ESP32.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("segundos", nargs="?", type=float, default=10.0)
    ap.add_argument("--filtro", default="")
    args = ap.parse_args()
    try:
        asyncio.run(main(args.segundos, args.filtro))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Erro no scan Bluetooth: {e}")
        print("No Raspberry: sudo systemctl start bluetooth  (e confira: bluetoothctl show)")
        sys.exit(1)
