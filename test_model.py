import os
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import cv2
import tensorflow as tf
import warnings


# Подавляем специфические предупреждения TensorFlow
warnings.filterwarnings("ignore", category=UserWarning, module='absl')

def load_model_with_metrics(model_path):
    """Загрузка модели с инициализацией метрик"""
    model = tf.keras.models.load_model(model_path)

    # Перекомпилируем модель с метриками
    model.compile(optimizer='adam',
                  loss='binary_crossentropy',
                  metrics=['accuracy',
                           tf.keras.metrics.Precision(name='precision'),
                           tf.keras.metrics.Recall(name='recall')])
    return model


def load_test_data(test_dir):
    """Загружаем и предобрабатываем тестовые данные"""
    images = []
    true_labels = []

    for class_name in ['free', 'occupied']:
        class_dir = os.path.join(test_dir, class_name)
        class_label = 0 if class_name == 'free' else 1

        if not os.path.exists(class_dir):
            print(f"Warning: Directory {class_dir} does not exist!")
            continue

        image_files = [f for f in os.listdir(class_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not image_files:
            print(f"Warning: No images found in {class_dir}")
            continue

        for img_name in image_files:
            img_path = os.path.join(class_dir, img_name)
            img = cv2.imread(img_path)

            if img is None:
                print(f"Warning: Could not read image {img_path}")
                continue

            if img.shape != (64, 64, 3):
                img = cv2.resize(img, (64, 64))
                if len(img.shape) == 2:  # Если grayscale
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

            try:
                # processed_img = preprocess_spot(img)
                # images.append(processed_img)
                images.append(img)
                true_labels.append(class_label)
            except Exception as e:
                print(f"Error processing {img_path}: {str(e)}")

    if not images:
        raise ValueError("No valid test images found in the test directory!")

    return np.array(images), np.array(true_labels)


def safe_predict(img: np.ndarray, model, threshold: float = 0.5) -> float:

    try:
        # Проверка и корректировка размерности
        if len(img.shape) == 2:  # Grayscale
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        elif img.shape[2] == 1:  # Single channel
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

        if img.shape != (64, 64, 3):
            img = cv2.resize(img, (64, 64))

        # Нормализация и добавление размерности батча
        img_input = np.expand_dims(img / 255.0, axis=0)

        return float(model.predict(img_input, verbose=0)[0][0])
    except Exception as e:
        print(f"Prediction error: {str(e)}")
        return 0.5

def evaluate_model(model, test_images, test_labels):
    """Полная оценка модели на тестовых данных"""
    # Предсказания
    pred_probs = []
    for img in test_images:
        try:
            prob = safe_predict(img, model)
            pred_probs.append(prob)
        except Exception as e:
            print(f"Prediction error: {str(e)}")
            pred_probs.append(0.5)

    pred_labels = (np.array(pred_probs) > 0.5).astype(int)

    # Оценка с помощью встроенных метрик модели
    print("\nModel internal evaluation:")
    test_loss, test_acc, test_precision, test_recall = model.evaluate(
        test_images, test_labels, verbose=0)
    print(f"Test Accuracy: {test_acc:.4f}")
    print(f"Test Precision: {test_precision:.4f}")
    print(f"Test Recall: {test_recall:.4f}")

    # Подробный отчет
    print("\nDetailed Classification Report:")
    print(classification_report(test_labels, pred_labels,
                                target_names=['free', 'occupied'],
                                digits=4))

    # Confusion matrix
    plt.figure(figsize=(8, 6))
    cm = confusion_matrix(test_labels, pred_labels)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=['free', 'occupied'],
                yticklabels=['free', 'occupied'])
    plt.xlabel('Predicted')
    plt.ylabel('True')
    plt.title('Confusion Matrix')
    plt.show()

    # Дополнительная статистика
    print("\nAdditional Statistics:")
    print(f"Total test samples: {len(test_labels)}")
    print(f"Free spots (true): {sum(test_labels == 0)}")
    print(f"Occupied spots (true): {sum(test_labels == 1)}")
    print(f"Model accuracy: {np.mean(test_labels == pred_labels):.4f}")



# Настройки
MODEL_PATH = 'models/parking_classifier.h5'
TEST_DIR = 'processed_bboxes/test'

try:
    # Загрузка модели с инициализацией метрик
    print("Loading model...")
    model = load_model_with_metrics(MODEL_PATH)

    # Проверка тестовой директории
    if not os.path.exists(TEST_DIR):
        raise FileNotFoundError(f"Test directory {TEST_DIR} does not exist!")

    # Загрузка тестовых данных
    print("Loading test data...")
    test_images, test_labels = load_test_data(TEST_DIR)

    # Оценка модели
    print("\nEvaluating model...")
    evaluate_model(model, test_images, test_labels)

except Exception as e:
    print(f"\nError: {str(e)}")
    print("Please check:")
    print(f"1. Model exists at {MODEL_PATH}")
    print(f"2. Test directory structure: {TEST_DIR}/free/ and {TEST_DIR}/occupied/")
    print(f"3. Test images are valid (PNG/JPG format)")