import cv2
import os
from tqdm import tqdm

# Параметры
TARGET_SIZE = (64, 64)
CLASSES = ['free', 'occupied']  # Подпапки


def process_and_overwrite(INPUT_DIR):
    for class_name in CLASSES:
        class_path = os.path.join(INPUT_DIR, class_name)
        image_files = [f for f in os.listdir(class_path) if f.endswith(('.jpg', '.png'))]

        for img_name in tqdm(image_files, desc=f'Обработка {class_name}'):
            img_path = os.path.join(class_path, img_name)

            # Чтение изображения
            img = cv2.imread(img_path)
            if img is None:
                print(f'Ошибка чтения: {img_path}')
                continue

            # Сохраняем пропорции с паддингом
            h, w = img.shape[:2]
            scale = TARGET_SIZE[0] / max(h, w)
            new_h, new_w = int(h * scale), int(w * scale)
            resized = cv2.resize(img, (new_w, new_h))

            # Добавляем чёрные границы
            delta_h = TARGET_SIZE[0] - new_h
            delta_w = TARGET_SIZE[1] - new_w
            top = delta_h // 2
            bottom = delta_h - top
            left = delta_w // 2
            right = delta_w - left

            padded = cv2.copyMakeBorder(
                resized,
                top, bottom, left, right,
                cv2.BORDER_CONSTANT,
                value=(0, 0, 0)  # Чёрный цвет
            )

            # Перезапись файла
            cv2.imwrite(img_path, padded)


process_and_overwrite('processed_bboxes/train')
process_and_overwrite('processed_bboxes/test')
