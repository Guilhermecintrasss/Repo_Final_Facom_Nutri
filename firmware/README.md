# Firmware do ESP32 (altura com LiDAR TF-Luna)

Sketch Arduino em [`esp32_lidar_ble/esp32_lidar_ble.ino`](esp32_lidar_ble/esp32_lidar_ble.ino).
A pasta tem o mesmo nome do `.ino`, como a Arduino IDE exige.

## Hardware
- ESP32 + sensor LiDAR **TF-Luna** (115200 baud).
- Ligações: TX do sensor → pino **16** (RX2) do ESP32; RX do sensor → pino **17** (TX2).

## Dependências (Arduino IDE)
- Suporte a placas ESP32 (inclui as bibliotecas `BLEDevice`, `BLEServer`, `BLEUtils`, `BLE2902`).
- Biblioteca **TFMPlus** (oficial do TF-Luna).

## Protocolo BLE (serviço UART Nordic)
O ESP32 anuncia com o nome **`ESP32_BLE`**.

| Característica | UUID | Direção | Uso |
|---|---|---|---|
| Serviço | `6E400001-B5A3-F393-E0A9-E50E24DCCA9E` | | |
| RX | `6E400002-...` | servidor (Flask) → ESP32, *write* | comandos |
| TX | `6E400003-...` | ESP32 → servidor, *notify* | resultado da medição |

**Comandos** (texto, 1 caractere):
- `M` — mede a altura: média de até 300 leituras do LiDAR (timeout 10 s) e envia o resultado.
- `C` — calibra: média de até 300 leituras com o espaço livre, guardada como distância do sensor ao chão (`alturaFixa`, padrão 213 cm; timeout 15 s).

**Resposta ao `M`** (notificação de 20 bytes, little-endian, `struct '<H9H'` em Python):
- `medida` (`uint16`): altura em **centésimos de cm** (`17234` = 172,34 cm) = `(alturaFixa − média_lida) × 100`.
- `leituras[9]` (`uint16`): as 9 primeiras distâncias lidas (cm), usadas para conferência.

O lado do servidor está em `app.py` (`notification_handler`). Para testar a conexão sem o Flask: `python testar_esp.py`.

## Observações sobre o comportamento atual
- `alturaFixa` fica só na RAM: ao reiniciar o ESP32 volta para 213 cm até uma nova calibração (`C`).
- A medição roda dentro do callback de escrita BLE e bloqueia por até 10 s (a calibração por até 15 s).
- Leituras fora de 0 < d < 250 cm são descartadas.
- Se a média lida for maior que `alturaFixa`, o resultado negativo estoura o `uint16` (valor errado).
