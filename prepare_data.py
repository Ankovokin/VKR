import os
import cv2
import pandas as pd
from tqdm import tqdm


# Вырезает каждое парковочное место в отдельный файл
def prepare_pklot_bboxes(src_dir="PKLot", dst_dir="processed_bboxes"):

    for split in ["train", "test", "valid"]:
        df = pd.read_csv(f"{src_dir}/{split}/labels.csv")

        for _, row in tqdm(df.iterrows(), total=len(df), desc=f"Processing {split}"):
            img_path = f"{src_dir}/{split}/{row['filename']}"
            img = cv2.imread(img_path)

            # Вырезаем bbox
            x1, y1, x2, y2 = row["xmin"], row["ymin"], row["xmax"], row["ymax"]
            spot_img = img[y1:y2, x1:x2]

            # Определяем класс
            class_dir = "free" if row["class"] == "space-empty" else "occupied"

            # Сохраняем
            spot_name = f"{row['filename'].split('.')[0]}_{x1}_{y1}.jpg"
            cv2.imwrite(f"{dst_dir}/{split}/{class_dir}/{spot_name}", spot_img)

prepare_pklot_bboxes()

