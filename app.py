from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO
import asyncio
import os
import time
import threading
import selectors
import struct
from bleak import BleakClient, BleakScanner
import shared

from static.functions import init_DB, get_db_connection

# Posições: [2]=Dezenas, [3]=Unidades, [5]=Décimos, [6]=Centésimos
POS_DIGITOS = [2, 3, 5, 6]
POS_DIGITOS_VALIDOS = [3, 5, 6]
BASE = 0x1F

import sys

try:
    import serial
except ImportError:
    print("Erro: pyserial não instalado.")
    print("  Execute: python -m pip install pyserial")
    sys.exit(1)

# No Raspberry o adaptador USB-serial aparece como /dev/ttyUSB0 (ou /dev/ttyACM0).
# Para um nome fixo, use /dev/serial/by-id/... (ls /dev/serial/by-id/).
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
    global tendencia_subindo, offset

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
                if shared.ultimo_valor_real > 60.0:
                    tendencia_subindo = True
                elif 60 > shared.ultimo_valor_real:
                    tendencia_subindo = False
                # =========================
                # DETECÇÃO DE ZERO AMBÍGUO
                # =========================
                # Dezena em branco: qualquer código que não seja dígito (7B, 63, 73...), exceto 6B (faixa 90)
                eh_zero_raw = decode_digito(pkt[2]) not in range(10) and pkt[2] != 0x6B
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

                shared.ultimo_valor_real = valor_final


def ler_continuo_com_retry():
    """Reabre a porta serial se o adaptador for desconectado ou ainda não existir."""
    while True:
        try:
            ler_continuo()
        except serial.SerialException as e:
            print(f"[balança] Erro serial ({PORTA}): {e} — nova tentativa em 3s")
        except Exception as e:
            print(f"[balança] Erro inesperado: {e} — nova tentativa em 3s")
        time.sleep(3)


app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'projetofacom'

init_DB()

# AJUSTE 1: Forçar o async_mode='threading' e permitir broadcast
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# No macOS o bleak usa um UUID gerado pelo CoreBluetooth; no Linux (BlueZ/Raspberry)
# é preciso o endereço MAC do ESP32 (AA:BB:CC:DD:EE:FF) ou o nome anunciado via BLE.
DEVICE_UUID = os.environ.get("ESP32_BLE_ADDRESS", "")
DEVICE_NAME = os.environ.get("ESP32_BLE_NAME", "")
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

esp32_client = None
selector = selectors.DefaultSelector()
loop = asyncio.SelectorEventLoop(selector)

def notification_handler(sender, data):
    mensagem_esp = struct.unpack('<H9H', data)
    medida_principal = float(mensagem_esp[0]) / 100.0
    lista_leituras = list(mensagem_esp[1:])
    #mensagem_esp = data.decode('utf-8').strip()
    print(f"Bluetooth diz: {medida_principal}, {lista_leituras}")
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO leituras_complexas (media_final, vetor_amostras) VALUES (%s, %s)", 
               (medida_principal, lista_leituras))
            conn.commit()
        except Exception as e:
            print(f"Erro ao inserir no banco: {e}")
        finally:
            conn.close()
    
    socketio.emit('dados_esp', {'valor': medida_principal})

def start_async_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

thread_ble = threading.Thread(target=start_async_loop, args=(loop,), daemon=True)
thread_ble.start()

# --- Thread 2: Balança Serial (ADICIONE ESTA) ---
thread_balanca = threading.Thread(target=ler_continuo_com_retry, daemon=True)
thread_balanca.start()

async def connect_to_esp():
    global esp32_client
    if esp32_client is None or not esp32_client.is_connected:
        try:
            alvo = DEVICE_UUID
            if not alvo and DEVICE_NAME:
                dispositivo = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=10.0)
                if dispositivo is None:
                    raise RuntimeError(f"ESP32 '{DEVICE_NAME}' não encontrado no scan BLE")
                alvo = dispositivo
            if not alvo:
                raise RuntimeError("Defina ESP32_BLE_ADDRESS (MAC) ou ESP32_BLE_NAME")
            esp32_client = BleakClient(alvo)
            await esp32_client.connect()
            await esp32_client.start_notify(UART_TX_CHAR_UUID, notification_handler)
            print("Conectado e ouvindo o ESP32!")
        except Exception as e:
            print(f"Erro ao conectar ao ESP32: {e}")
            socketio.emit('erro_esp', {'detalhes': str(e)})
    return esp32_client

@app.route('/enviar', methods=['POST'])
def enviar_comando():
    dados = request.json
    mensagem = dados.get("mensagem", "")
    if not mensagem:
        return jsonify({"erro": "Mensagem vazia"}), 400
    
    try:
        asyncio.run_coroutine_threadsafe(send_ble_data(mensagem), loop)
        return jsonify({"status": "sucesso", "enviado": mensagem})
    except Exception as e:
        return jsonify({"status": "erro", "detalhes": str(e)}), 500


async def send_ble_data(msg):
    try:
        client = await connect_to_esp()
        await client.write_gatt_char(UART_RX_CHAR_UUID, msg.encode())
    except Exception as e:
        socketio.emit('erro_esp', {'detalhes': str(e)})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dados')
def dados():
    conn = get_db_connection()
    if not conn:
        return "Erro ao conectar ao banco de dados", 500
    
    try:
        cur = conn.cursor()
        # Buscamos os dados
        cur.execute("SELECT id, media_final, vetor_amostras, medido_em FROM leituras_complexas ORDER BY id DESC LIMIT 10")
        resultado = cur.fetchall()
        print(f"Dados da balança: {resultado}")
        cur.execute("SELECT * FROM registros_balanca ORDER BY id DESC LIMIT 10")
        resultado_balanca = cur.fetchall()
        print(f"Dados da balança (registros_balanca): {resultado_balanca}")
        # Formatamos para uma lista de dicionários
        lista_formatada = [
            {
                "id": r[0],
                "media_final": r[1], 
                "vetor_amostras": r[2], 
                "medido_em": r[3].strftime('%d/%m/%Y %H:%M:%S') # Formata data bonita
            } for r in resultado
        ]
        
        # Formatamos para uma lista de dicionários
        lista_formatada_balanca = [
            {
                "id": r[0],
                "valor_visor": r[1],
                "imagem1": r[2],
                "imagem2": r[3],
                "imagem3": r[4],
                "medido_em": r[5].strftime('%d/%m/%Y %H:%M:%S')  # Formata data bonita
            } for r in resultado_balanca
        ]

        return render_template('tabela.html', leituras=lista_formatada, balanca=lista_formatada_balanca)

    except Exception as e:
        return f"Erro ao consultar o banco: {e}", 500
    finally:
        conn.close()

from routes.peso import PesoRoute

app.register_blueprint(PesoRoute)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)