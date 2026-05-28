import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import os

# Параметры
IMG_SIZE = (64, 64)
BATCH_SIZE = 32
EPOCHS = 30  # увеличили, EarlyStopping сам остановит

# Проверка наличия данных
print("Проверка структуры данных...")
class_counts = {}
for folder in ['train', 'test']:
    path = f'processed_bboxes/{folder}'
    if not os.path.exists(path):
        raise FileNotFoundError(f"Папка {path} не найдена!")
    for cls in ['free', 'occupied']:
        cls_path = os.path.join(path, cls)
        if not os.path.exists(cls_path):
            raise FileNotFoundError(f"Папка класса {cls_path} не найдена!")
        num_files = len(os.listdir(cls_path))
        print(f"{cls_path}: {num_files} изображений")
        if folder == 'train':
            class_counts[cls] = num_files

# Вычисляем веса классов автоматически
total = sum(class_counts.values())
class_weight = {
    0: total / (2 * class_counts['free']),      # free = 0
    1: total / (2 * class_counts['occupied'])   # occupied = 1
}
print(f"\nВеса классов: free={class_weight[0]:.2f}, occupied={class_weight[1]:.2f}")

# Генераторы данных (без изменений)
train_datagen = ImageDataGenerator(
    rescale=1. / 255,
    rotation_range=10,
    width_shift_range=0.1,
    height_shift_range=0.1,
    shear_range=0.1,
    zoom_range=0.1,
    horizontal_flip=True,
    validation_split=0.2
)
test_datagen = ImageDataGenerator(rescale=1. / 255)

train_data = train_datagen.flow_from_directory(
    'processed_bboxes/train',
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='binary',
    subset='training',
    seed=42
)
valid_data = train_datagen.flow_from_directory(
    'processed_bboxes/train',
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='binary',
    subset='validation',
    seed=42
)
test_data = test_datagen.flow_from_directory(
    'processed_bboxes/test',
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='binary',
    shuffle=False
)

print(f"\nКлассы: {train_data.class_indices}")
print(f"Обучающая: {train_data.samples} | Валидационная: {valid_data.samples} | Тестовая: {test_data.samples}")

# Модель (без изменений)
model = tf.keras.Sequential([
    tf.keras.layers.Conv2D(32, (3, 3), activation='relu', input_shape=(64, 64, 3)),
    tf.keras.layers.BatchNormalization(),
    tf.keras.layers.MaxPooling2D(2, 2),

    tf.keras.layers.Conv2D(64, (3, 3), activation='relu'),
    tf.keras.layers.BatchNormalization(),
    tf.keras.layers.MaxPooling2D(2, 2),

    tf.keras.layers.Conv2D(128, (3, 3), activation='relu'),
    tf.keras.layers.BatchNormalization(),
    tf.keras.layers.MaxPooling2D(2, 2),

    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dropout(0.5),
    tf.keras.layers.Dense(1, activation='sigmoid')
])

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss='binary_crossentropy',
    metrics=['accuracy',
             tf.keras.metrics.Precision(name='precision'),
             tf.keras.metrics.Recall(name='recall'),
             tf.keras.metrics.AUC(name='auc')]
)

# Callbacks — EarlyStopping + снижение lr при застревании
callbacks = [
    EarlyStopping(
        monitor='val_loss',
        patience=5,
        restore_best_weights=True,
        verbose=1
    ),
    ReduceLROnPlateau(
        monitor='val_loss',
        factor=0.5,
        patience=3,
        min_lr=1e-6,
        verbose=1
    )
]

# Обучение с весами классов
print("\nОбучение модели...")
history = model.fit(
    train_data,
    validation_data=valid_data,
    epochs=EPOCHS,
    callbacks=callbacks,
    class_weight=class_weight,  # ← главное добавление
    verbose=1
)

# Остальное без изменений...
model.save("models/parking_classifier.h5")
print("\nМодель сохранена!")