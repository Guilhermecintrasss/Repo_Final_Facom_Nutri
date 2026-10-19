"""Diagnóstico da porta serial da balança.

Testa vários baud rates e formatos (bits/paridade) e mostra os bytes recebidos.
Pacote válido da Welmy W200: 4800 baud, 7E1, bytes < 0x80, terminado em 0x00.

Uso: python diag_serial.py [porta] [segundos_por_teste]
"""
import os
import sys
import time

try:
    import serial
except ImportError:
    print("pyserial não instalado: pip install pyserial")
    sys.exit(1)

PORTA = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BALANCA_PORT", "/dev/ttyUSB0")
SEGUNDOS = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5

FORMATOS = {
    "7E1": (serial.SEVENBITS, serial.PARITY_EVEN),
    "8N1": (serial.EIGHTBITS, serial.PARITY_NONE),
    "7O1": (serial.SEVENBITS, serial.PARITY_ODD),
    "7N1": (serial.SEVENBITS, serial.PARITY_NONE),
}
BAUDS = (4800, 9600, 2400, 1200, 19200)


def testar(baud, bits, paridade):
    with serial.Serial(PORTA, baud, bytesize=bits, parity=paridade,
                       stopbits=serial.STOPBITS_ONE, timeout=0.1) as s:
        s.reset_input_buffer()
        dados = b""
        fim = time.time() + SEGUNDOS
        while time.time() < fim:
            dados += s.read(s.in_waiting or 1)
    return dados


def main():
    print(f"Porta: {PORTA} | {SEGUNDOS}s por teste | coloque a balança ligada, com peso\n")
    print(f"{'config':<10}{'bytes':>6}  {'tem 00':<7}{'todos<80':<9}amostra (hex)")
    melhores = []
    for baud in BAUDS:
        for nome, (bits, par) in FORMATOS.items():
            try:
                d = testar(baud, bits, par)
            except serial.SerialException as e:
                print(f"Erro ao abrir {PORTA}: {e}")
                sys.exit(1)
            tem_zero = b"\x00" in d
            baixos = bool(d) and all(b < 0x80 for b in d)
            variacao = len(set(d))
            print(f"{baud} {nome:<5}{len(d):>6}  {str(tem_zero):<7}{str(baixos):<9}{d[:20].hex(' ')}")
            if tem_zero and baixos and variacao > 2:
                melhores.append(f"{baud} {nome}")
    print()
    if melhores:
        print("Configurações com aparência de pacotes válidos:", ", ".join(melhores))
    else:
        print("Nenhuma config parece válida. Se só aparecem FF/F7 ou nada, a balança não está")
        print("transmitindo: confira cabo, TX/RX, alimentação e modo de transmissão da balança.")


if __name__ == "__main__":
    main()
