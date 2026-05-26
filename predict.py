import cv2
import numpy as np
from ultralytics import YOLO
import tensorflow as tf
#
# Загрузка моделей
yolo = YOLO("models/yolov8n.pt")
classifier = tf.keras.models.load_model("models/parking_classifier.h5")
#
#
def load_spots(file_path):
    spots = []
    with open(file_path) as f:
        for line in f:
            x1, y1, x2, y2 = map(int, line.strip().split(","))
            spots.append((x1, y1, x2, y2))
    return spots
#
#
# def predict_parking(image_path, spots_file, threshold=0.2):
#     img = cv2.imread(image_path)
#     spots = load_spots(spots_file)
#
#     # Детекция авто
#     results = yolo.predict(img, classes=[2, 5, 7])  # cars, buses, trucks
#
#     free = 0
#     for i, (x1, y1, x2, y2) in enumerate(spots):
#         spot_img = img[y1:y2, x1:x2]
#         spot_img = cv2.resize(spot_img, (64, 64))
#         spot_img = spot_img / 255.0
#         spot_img = np.expand_dims(spot_img, axis=0)
#
#         # Классификация
#         pred = classifier.predict(spot_img)[0][0]
#         if pred < threshold:  # Используем настраиваемый порог
#             free += 1
#             color = (0, 255, 0)
#         else:
#             color = (0, 0, 255)
#
#         cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
#
#     cv2.putText(img, f"Free: {free}/{len(spots)}", (10, 30),
#                 cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
#     cv2.imshow("Result", img)
#     cv2.waitKey(0)
#
#


# def show_yolo_detections(image_path):
#     img = cv2.imread(image_path)
#     results = yolo.predict(img, classes=[2, 5, 7])  # 2=car, 5=bus, 7=truck
#     for box in results[0].boxes:
#         x1, y1, x2, y2 = map(int, box.xyxy[0])
#         cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
#     cv2.imshow("YOLO Detections", img)
#     cv2.waitKey(0)




def predict_parking(image_path, spots_file, threshold=0.99):#0.95
    img = cv2.imread(image_path)
    spots = load_spots(spots_file)

    # Детекция авто YOLO
    yolo_results = yolo.predict(img, classes=[2], conf=0.3, iou=0.45, verbose=False) #0.5
    yolo_boxes = [box.xyxy[0].cpu().numpy() for box in yolo_results[0].boxes]

    free = 0
    for i, (x1, y1, x2, y2) in enumerate(spots):
        spot_box = np.array([x1, y1, x2, y2])

        # Проверка пересечения с YOLO-боксами
        is_occupied_yolo = any(check_box_overlap(spot_box, yolo_box)
                               for yolo_box in yolo_boxes)

        if is_occupied_yolo:
            is_occupied_classifier = True
        else:
            spot_img = img[y1:y2, x1:x2]
            spot_img = cv2.resize(spot_img, (64, 64)) / 255.0
            pred = classifier.predict(np.expand_dims(spot_img, axis=0))[0][0]
            is_occupied_classifier = pred >= threshold

        if is_occupied_classifier:
            color = (0, 0, 255)
        else:
            free += 1
            color = (0, 255, 0)

        if is_occupied_yolo:
            color = (255, 0, 0)

        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

    cv2.putText(img, f"Free: {free}/{len(spots)}", (10, 30),
                                 cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imshow("Result", img)
    cv2.waitKey(0)


def check_box_overlap(box1, box2):
    """Проверка пересечения двух bounding box"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    return x1 < x2 and y1 < y2

# одноразовая проверка
# show_yolo_detections("test3.jpg")
predict_parking("test4.jpg", "spots2.txt")