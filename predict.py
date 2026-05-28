import cv2
import numpy as np
from ultralytics import YOLO
import tensorflow as tf
#
# Загрузка моделей
# yolo = YOLO("models/yolov8n.pt")
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


def predict_parking_video(video_path, spots_file, threshold=0.5):
    spots = load_spots(spots_file)
    cap = cv2.VideoCapture(video_path)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Батчевая классификация всех мест
        patches = []
        for (x1, y1, x2, y2) in spots:
            patch = frame[y1:y2, x1:x2]
            if patch.size == 0:
                patches.append(np.zeros((64, 64, 3)))
                continue
            patch = cv2.resize(patch, (64, 64)) / 255.0
            patches.append(patch)

        preds = classifier.predict(np.array(patches), verbose=0)

        free = 0
        occupied = 0
        for i, (x1, y1, x2, y2) in enumerate(spots):
            is_occupied = preds[i][0] >= threshold

            if is_occupied:
                occupied += 1
                color = (0, 0, 255)    # красный
            else:
                free += 1
                color = (0, 255, 0)    # зелёный

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            # Номер места
            cv2.putText(frame, str(i+1), (x1+2, y1+15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # Сводка
        cv2.putText(frame, f"Free: {free}  Occupied: {occupied}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    1, (255, 255, 255), 2)
        cv2.imshow("Parking", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

predict_parking_video("video_test5.mp4", "spots5.txt")