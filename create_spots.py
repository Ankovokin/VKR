import cv2
import numpy as np
from fontTools.misc.cython import returns

# Берём первый кадр из видео
cap = cv2.VideoCapture("video_test.mp4")
ret, frame = cap.read()
cap.release()

spots = []
start_point = None
current_frame = frame.copy()

def draw_rectangle(event, x, y, flags, param):
    global start_point, current_frame

    if event == cv2.EVENT_LBUTTONDOWN:
        # Запоминаем начало прямоугольника
        start_point = (x, y)

    elif event == cv2.EVENT_LBUTTONUP and start_point:
        # Конец прямоугольника — сохраняем
        x1, y1 = start_point
        x2, y2 = x, y
        # Убеждаемся что x1<x2 и y1<y2
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        spots.append((x1, y1, x2, y2))
        cv2.rectangle(current_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(current_frame, str(len(spots)), (x1, y1-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
        cv2.imshow("Mark spots", current_frame)
        print(f"Место {len(spots)}: {x1},{y1},{x2},{y2}")
        start_point = None

    elif event == cv2.EVENT_MOUSEMOVE and start_point:
        # Показываем прямоугольник в процессе рисования
        temp = current_frame.copy()
        cv2.rectangle(temp, start_point, (x, y), (255, 255, 0), 1)
        cv2.imshow("Mark spots", temp)

cv2.imshow("Mark spots", frame)
cv2.setMouseCallback("Mark spots", draw_rectangle)

print("S = сохранить, Q = выйти")

while True:
    key = cv2.waitKey(1) & 0xFF
    if key == ord('s'):
        with open("spots3.txt", "w") as f:
            for (x1, y1, x2, y2) in spots:
                f.write(f"{x1},{y1},{x2},{y2}\n")
        print(f"Сохранено {len(spots)} мест в spots.txt")
    elif key == ord('q'):
        break


cv2.destroyAllWindows()