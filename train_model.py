import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import os

# Параметры
IMG_SIZE = (64, 64)
BATCH_SIZE = 32
EPOCHS = 10

# Проверка наличия данных
print("Проверка структуры данных...")
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

# Генераторы данных
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

# Загрузка данных
print("\nЗагрузка данных...")
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

# Проверка баланса классов
print("\nБаланс классов:")
print(f"Обучающая выборка: {train_data.samples} образцов")
print(f"Валидационная выборка: {valid_data.samples} образцов")
print(f"Тестовая выборка: {test_data.samples} образцов")

# Модель
print("\nСоздание модели...")
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
    metrics=[
        'accuracy',
        tf.keras.metrics.Precision(name='precision'),
        tf.keras.metrics.Recall(name='recall'),
        tf.keras.metrics.AUC(name='auc')
    ]
)

# Обучение
print("\nОбучение модели...")
history = model.fit(
    train_data,
    validation_data=valid_data,
    epochs=EPOCHS,
    verbose=1
)

# Сохранение модели
model.save("models/parking_classifier.h5")
print("\nМодель успешно сохранена!")

# Оценка на тестовых данных
print("\nОценка на тестовых данных...")
test_loss, test_acc, test_precision, test_recall, test_auc = model.evaluate(test_data)
print(f"\nТестовая точность: {test_acc:.4f}")
print(f"Тестовая precision: {test_precision:.4f}")
print(f"Тестовая recall: {test_recall:.4f}")
print(f"Тестовый AUC: {test_auc:.4f}")

# Подробный отчет
print("\nГенерация подробного отчета...")
test_data.reset()  # Сброс генератора
predictions = model.predict(test_data)
pred_labels = (predictions > 0.5).astype(int)

print("\nClassification Report:")
print(classification_report(test_data.classes, pred_labels,
                            target_names=['free', 'occupied'],
                            digits=4))

# Confusion matrix
cm = confusion_matrix(test_data.classes, pred_labels)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['free', 'occupied'],
            yticklabels=['free', 'occupied'])
plt.xlabel('Predicted')
plt.ylabel('True')
plt.title('Confusion Matrix')
plt.show()

# Графики обучения
plt.figure(figsize=(12, 5))
plt.subplot(1, 2, 1)
plt.plot(history.history['accuracy'], label='Train Accuracy')
plt.plot(history.history['val_accuracy'], label='Validation Accuracy')
plt.title('Accuracy over Epochs')
plt.legend()

plt.subplot(1, 2, 2)
plt.plot(history.history['loss'], label='Train Loss')
plt.plot(history.history['val_loss'], label='Validation Loss')
plt.title('Loss over Epochs')
plt.legend()
plt.show()

print("\nПроверка завершена!")