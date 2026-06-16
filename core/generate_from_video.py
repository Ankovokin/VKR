import cv2
import os

def generate_from_video(video_path, spots_file, output_dir="processed_bboxes",
                         frame_step=150):

    # Читаем координаты мест
    spots = []
    with open(spots_file) as f:
        for line in f:
            x1, y1, x2, y2 = map(int, line.strip().split(","))
            spots.append((x1, y1, x2, y2))

    cap = cv2.VideoCapture(video_path)
    frame_idx = 0
    saved = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_step == 0:
            for i, (x1, y1, x2, y2) in enumerate(spots):
                patch = frame[y1:y2, x1:x2]
                if patch.size == 0:
                    continue
                patch = cv2.resize(patch, (64, 64))
                # 80% в train, 20% в test
                #split = "train" if saved % 5 != 0 else "test"

                out_path = f"{output_dir}/to_label/spot{i}_frame{frame_idx}.jpg"
                os.makedirs(f"{output_dir}/to_label", exist_ok=True)
                cv2.imwrite(out_path, patch)
                saved += 1

        frame_idx += 1

    cap.release()
    print(f"Сохранено {saved} патчей в {output_dir}/to_label/")

generate_from_video("../vid_frags/video_test5.mp4", "spots/spots5.txt")