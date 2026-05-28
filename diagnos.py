import cv2

# 1. Проверка разрешение видео
cap = cv2.VideoCapture("video_test.mp4")
ret, frame = cap.read()
print(f"Разрешение видео: ширина={frame.shape[1]}, высота={frame.shape[0]}")
cap.release()

# 2. Содержимое спотс файла
with open("spots3.txt") as f:
    lines = f.readlines()
    print(f"\nКоличество мест: {len(lines)}")
    print("Первые 5 записей:")
    for line in lines[:5]:
        print(" ", line.strip())