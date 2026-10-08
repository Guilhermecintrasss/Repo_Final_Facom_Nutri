import cv2

def listar_cameras():
    index = 0
    arr = []
    # Testamos os primeiros 5 índices
    while index < 5:
        cap = cv2.VideoCapture(index)
        if cap.read()[0]:
            arr.append(index)
            cap.release()
        index += 1
    return arr

print(f"Câmeras detectadas nos índices: {listar_cameras()}")