# Posições: [2]=Dezenas, [3]=Unidades, [5]=Décimos, [6]=Centésimos
POS_DIGITOS = [2, 3, 5, 6]
POS_DIGITOS_VALIDOS = [3, 5, 6]
BASE = 0x1F

import os
import sys

try:
    import serial
except ImportError:
    print("Erro: pyserial não instalado.")
    print("  Execute: python -m pip install pyserial")
    sys.exit(1)

PORTA = os.environ.get("BALANCA_PORT", "/dev/ttyUSB0")
BAUD  = 4800
# A balança não envia paridade par de verdade (~40% dos bytes falhariam em 7E1). No Linux o
# kernel troca bytes com erro de paridade por 0x00, quebrando os pacotes. Por isso abrimos em
# 8N1 e removemos o bit alto (& 0x7F) ao ler, o que equivale ao que o macOS entregava.
CFG   = dict(bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)


# =========================
# ESTADO GLOBAL
# =========================
tendencia_subindo = False
ultimo_valor_real = 0.0
offset = 0


def decode_digito(b: int) -> int:
    # Os bytes finais do pacote às vezes chegam deslocados à esquerda (1F -> 3E -> 7C).
    # Os dígitos válidos são <= 0x1F, então dá para desfazer até 2 deslocamentos.
    original = b
    for _ in range(3):
        d = (BASE - b) // 2
        if 0 <= d <= 9:
            return d
        if b == 0 or b & 1:
            break
        b >>= 1
    return (BASE - original) // 2


def decode_peso(pkt: bytes):
    if len(pkt) < 7:
        return None
    
    d = [decode_digito(pkt[p]) for p in POS_DIGITOS]
    d_validos = [decode_digito(pkt[p]) for p in POS_DIGITOS_VALIDOS]

    d2 = decode_digito(pkt[2])

    # Se dezenas inválida, força 0
    if d2 < 0 or d2 > 9:
        d[0] = 0

    # Validação
    if any(v < 0 or v > 9 for v in d_validos):
        return None

    return tuple(d)


def calcular_valor(d2, d3, d5, d6):
    return (d2 * 10) + d3 + (d5 * 0.1) + (d6 * 0.01)


def ler_continuo():
    global tendencia_subindo, ultimo_valor_real, offset

    print(f"\nWelmy W200 — {BAUD} baud 8N1 (7 bits úteis) — {PORTA}")
    print("Ctrl+C para sair.\n")

    buf = b""
    ultimo_peso_bruto = None

    with serial.Serial(port=PORTA, baudrate=BAUD, timeout=0.1, **CFG) as ser:
        ser.reset_input_buffer()

        while True:
            raw = ser.read(ser.in_waiting or 1)
            if raw:
                buf += bytes(x & 0x7F for x in raw)

            while b"\x00" in buf:
                pkt, buf = buf.split(b"\x00", 1)

                if len(pkt) < 7:
                    continue

                # Só o campo de peso tem 0x27 (ponto decimal) no byte 4; os demais são ignorados
                if len(pkt) > 4 and pkt[4] != 0x27:
                    continue

                resultado = decode_peso(pkt)

                if resultado is None:
                    hex_str = " ".join(f"{b:02X}" for b in pkt)
                    print(f"  [pacote inválido]: {hex_str}")
                    continue

                d2, d3, d5, d6 = resultado
                valor = calcular_valor(d2, d3, d5, d6)

                # =========================
                # DETECÇÃO DE TENDÊNCIA
                # =========================
                if ultimo_valor_real > 60.0:
                    tendencia_subindo = True
                elif 60 > ultimo_valor_real:
                    tendencia_subindo = False
                # =========================
                # DETECÇÃO DE ZERO AMBÍGUO
                # =========================
                # Dezena em branco chega como 7B, 63 ou 73 (bits deslocados do mesmo código)
                eh_zero_raw = pkt[2] in (0x7B, 0x63, 0x73)
                offset = 0
                # =========================
                # DETECÇÃO DE FAIXA 90KG
                # =========================
                if pkt[2] == 0x6B:
                    offset = 90

                if pkt[1] == 0x1D:
                    offset = 100

                # =========================
                # TRATAMENTO DO ZERO
                # =========================
                if tendencia_subindo and eh_zero_raw:
                  offset = 80

                # =========================
                # APLICA OFFSET
                # =========================
                valor_final = valor + offset

                ultimo_valor_real = valor_final

                # =========================
                # PRINT SOMENTE SE MUDAR
                # =========================
                if resultado != ultimo_peso_bruto:
                    hex_str = " ".join(f"{b:02X}" for b in pkt)
                    print(f"Peso: {valor_final:.2f} kg  ({valor_final*1000:.0f}g)   raw: {hex_str}")

                    ultimo_peso_bruto = resultado


if __name__ == "__main__":
    try:
        ler_continuo()
    except serial.SerialException as e:
        print(f"Erro serial: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nEncerrando.")