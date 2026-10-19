import psycopg2
import os
import cv2
import datetime
import sys

from dotenv import load_dotenv

# macOS usa AVFoundation; no Linux/Raspberry Pi o backend é o V4L2.
# Use CAMERA_INDEX para escolher a webcam (veja listarCameras.py ou `ls /dev/video*`).
CAMERA_BACKEND = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_V4L2
CAMERA_INDEX = int(os.environ.get("CAMERA_INDEX", "0"))
camera = cv2.VideoCapture(CAMERA_INDEX, CAMERA_BACKEND)
camera.set(cv2.CAP_PROP_EXPOSURE, -5)
camera.set(cv2.CAP_PROP_FPS, 45)
print(f"Câmera aberta: {camera.isOpened()}")

def get_db_connection():
    load_dotenv()
    try:
        DB_USER = os.environ.get('DB_USER', 'admin')
        DB_PASS = os.environ.get('DB_PASS', 'admin123')
        DB_HOST = os.environ.get('DB_HOST', 'localhost')
        DB_PORT = os.environ.get('DB_PORT', '5432')
        DB_NAME = os.environ.get('DB_NAME', 'CadNutriDB')
        print(DB_HOST)
        # Conecta ao banco
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"erro ao conectar: {e}")
        return None

def init_DB():
    try:
        conn = get_db_connection()
        if not conn:
            return 'Erro ao conectar ao Banco de Dados'
    
        cur = conn.cursor()
        f = open('./database/bancoInit.sql', 'r')
        sql_scripts = f.read()
        sql_scripts = sql_scripts.split(';')
        for script in sql_scripts:
            if script.strip():
                cur.execute(script)
        conn.commit()
        print(f"Banco inicializado com sucesso")
        return f"Banco inicializado com sucesso!"
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Erro ao executar o script SQL: {e}")
        return f"Erro ao executar o script SQL: {e}"
    finally:
        if conn:
            conn.close()



def capturar_estabilizado(nome_arquivo):
    frames = []
    for _ in range(15): # Captura 5 frames rápidos
        success, frame = camera.read()
        if success:
            frames.append(frame.astype(float))
    
    if not frames:
        return None

    # Faz a média aritmética dos frames
    res = sum(frames) / len(frames)
    cv2.imwrite(os.path.join('static/captures', nome_arquivo), res)
    return os.path.join('static/captures', nome_arquivo)

def capturar_3_frames():
    frames = []
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for caminho in range(3): # Captura 3 frames rápidos
        path = capturar_estabilizado(f"peso_{timestamp}_{caminho}.jpg")
        frames.append(path)
    return frames


def gen_frames():  
    while True:
        success, frame = camera.read()  # Lê o frame da webcam
        if not success:
            break
        else:
            # Codifica o frame em formato JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            
            # Formato necessário para o streaming MJPEG
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
