from flask import Blueprint, render_template, jsonify, Response
from flask_socketio import emit
from static.functions import get_db_connection, gen_frames, capturar_3_frames 

import shared

PesoRoute = Blueprint("Peso", __name__)


@PesoRoute.route("/medir_peso", methods=['POST'])
def medir_peso():
  caminhos = capturar_3_frames()
  # O offset de 80/90/100 kg já é aplicado na leitura da balança (app.py)
  valor = shared.ultimo_valor_real
  print(f"Valor capturado: {valor:.2f} kg")
  conn = get_db_connection()
  if not conn:
    return jsonify({"status": "erro", "detalhes": "Erro ao conectar ao banco de dados"}), 500
  try:
    cur = conn.cursor()
    cur.execute("INSERT INTO registros_balanca (valor_visor, imagem1, imagem2, imagem3) VALUES (%s, %s, %s, %s)", 
      (valor, caminhos[0], caminhos[1], caminhos[2]))
    conn.commit()
    emit('dados_balanca', {'valor': valor}, namespace='/', broadcast=True)
  except Exception as e:
    return jsonify({"status": "erro", "detalhes": f"Erro ao salvar no banco: {e}"}), 500
  finally:
    conn.close()
  return jsonify({"status": "sucesso", "enviado": valor})

@PesoRoute.route('/video_feed')
def video_feed():
  # Retorna a resposta de streaming
  return Response(gen_frames(),
    mimetype='multipart/x-mixed-replace; boundary=frame')

@PesoRoute.route("/configurar_webcam")
def configurar_webcam():
  return render_template('webcam.html')