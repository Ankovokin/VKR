import cv2

# Загрузка изображения
image = cv2.imread("test4.jpg")
spots = []

# Функция для обработки кликов мыши
def click_event(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        spots.append((x, y))
        print(f"Добавлена точка: ({x}, {y})")
        cv2.circle(image, (x, y), 5, (0, 0, 255), -1)
        cv2.imshow("Image", image)

# Отображение изображения и сбор точек
cv2.imshow("Image", image)
cv2.setMouseCallback("Image", click_event)
cv2.waitKey(0)
cv2.destroyAllWindows()

# Сохранение в файл
with open("spots2.txt", "w") as f:
    for i in range(0, len(spots), 2):
        x1, y1 = spots[i]
        x2, y2 = spots[i+1]
        f.write(f"{x1},{y1},{x2},{y2}\n")
print("Файл spots.txt сохранён!")