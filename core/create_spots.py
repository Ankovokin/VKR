import cv2
import os
import argparse


def load_existing_spots(filepath):
    """Загружает существующие места из файла"""
    spots = []
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            for line in f:
                x1, y1, x2, y2 = map(int, line.strip().split(","))
                spots.append((x1, y1, x2, y2))
        print(f"Загружено {len(spots)} мест из {filepath}")
    return spots


def save_spots(spots, filepath):
    """Сохраняет места в файл"""
    with open(filepath, "w") as f:
        for (x1, y1, x2, y2) in spots:
            f.write(f"{x1},{y1},{x2},{y2}\n")
    print(f"Сохранено {len(spots)} мест в {filepath}")


def draw_all_spots(frame, spots, show_numbers=True, highlight_idx=None):
    """Отрисовывает все прямоугольники и номера"""
    for idx, (x1, y1, x2, y2) in enumerate(spots):
        # Выделяем выбранное место другим цветом
        if highlight_idx == idx:
            color = (255, 255, 0)  # Жёлтый для выбранного
            thickness = 3
        else:
            color = (0, 255, 0)  # Зелёный для обычных
            thickness = 2

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
        if show_numbers:
            # Номер места в левом верхнем углу прямоугольника
            cv2.putText(frame, str(idx + 1), (x1 + 2, y1 + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


class SpotEditor:
    def __init__(self, video_path, spots_file):
        self.video_path = video_path
        self.spots_file = spots_file
        self.spots = []
        self.start_point = None
        self.show_numbers = True
        self.selected_spot = -1  # Индекс выбранного места (-1 = ничего не выбрано)
        self.mode = "draw"  # draw, delete_mode, clear_confirm

        # Загружаем видео
        self.cap = cv2.VideoCapture(video_path)
        ret, self.frame = self.cap.read()
        if not ret:
            raise ValueError("Не удалось прочитать видео")
        self.cap.release()

        # Загружаем существующие места
        self.spots = load_existing_spots(spots_file)

        # Создаём окно
        cv2.namedWindow("Parking spot editor")
        cv2.setMouseCallback("Parking spot editor", self.mouse_callback)

    def mouse_callback(self, event, x, y, flags, param):
        """Обработчик событий мыши"""
        # Режим удаления (D - mode delete)
        if self.mode == "delete_mode":
            if event == cv2.EVENT_LBUTTONDOWN:
                # Проверяем, на какое место нажали
                for idx, (x1, y1, x2, y2) in enumerate(self.spots):
                    if x1 <= x <= x2 and y1 <= y <= y2:
                        self.delete_spot_by_index(idx)
                        break
            return

        # Обычный режим рисования
        if event == cv2.EVENT_LBUTTONDOWN:
            self.start_point = (x, y)

        elif event == cv2.EVENT_LBUTTONUP and self.start_point:
            x1, y1 = self.start_point
            x2, y2 = x, y
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)

            if (x2 - x1) > 20 and (y2 - y1) > 20:
                self.spots.append((x1, y1, x2, y2))
                print(f"Добавлено место {len(self.spots)}: {x1},{y1},{x2},{y2}")
                self.update_display()
            else:
                print(f"Прямоугольник слишком мал, пропущен (размер: {x2 - x1}x{y2 - y1})")

            self.start_point = None

        elif event == cv2.EVENT_MOUSEMOVE and self.start_point:
            temp = self.get_display_frame()
            cv2.rectangle(temp, self.start_point, (x, y), (255, 255, 0), 1)
            cv2.imshow("Parking spot editor", temp)

    def get_display_frame(self):
        """Возвращает кадр с отрисованными местами"""
        frame_copy = self.frame.copy()
        draw_all_spots(frame_copy, self.spots, self.show_numbers, self.selected_spot)

        # Добавляем подсказки внизу экрана
        h, w = frame_copy.shape[:2]
        cv2.rectangle(frame_copy, (0, h - 100), (w, h), (0, 0, 0), -1)

        # Базовые команды
        y_offset = h - 90
        commands = [
            "S: Save | Q: Quit | H: Hide/Show numbers",
            f"Spots: {len(self.spots)} | Numbers: {'ON' if self.show_numbers else 'OFF'}"
        ]

        # Разные режимы
        if self.mode == "delete_mode":
            commands.append(" DELETE MODE: Click on spot to delete | ESC to exit mode")
            cv2.rectangle(frame_copy, (0, h - 100), (w, h), (0, 0, 255), 2)
        elif self.mode == "clear_confirm":
            commands.append(" DELETE ALL? Press Y to confirm, N to cancel")
            cv2.rectangle(frame_copy, (0, h - 100), (w, h), (0, 0, 255), 3)
        else:
            commands.append("D: Delete mode (click on spot) | C: Clear all spots | R: Reset mode")

        for i, cmd in enumerate(commands):
            cv2.putText(frame_copy, cmd, (10, y_offset + i * 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Показываем количество мест вверху
        cv2.putText(frame_copy, f"Spots: {len(self.spots)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Если выбран режим удаления, показываем дополнительный текст
        if self.mode == "delete_mode":
            cv2.putText(frame_copy, "DELETE MODE ACTIVE", (w - 250, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        return frame_copy

    def update_display(self):
        """Обновляет отображение в окне"""
        display_frame = self.get_display_frame()
        cv2.imshow("Parking spot editor", display_frame)

    def delete_spot_by_index(self, idx):
        """Удаляет место по индексу"""
        if 0 <= idx < len(self.spots):
            removed = self.spots.pop(idx)
            print(f"Удалено место {idx + 1}: {removed}")
            self.selected_spot = -1
            self.update_display()
            return True
        return False

    def delete_last_spot(self):
        """Удаляет последнее место"""
        if self.spots:
            self.delete_spot_by_index(len(self.spots) - 1)
        else:
            print("Нет мест для удаления")

    def toggle_delete_mode(self):
        """Включает/выключает режим удаления кликом по месту"""
        if self.mode == "delete_mode":
            self.mode = "draw"
            print("Режим удаления выключен")
        else:
            self.mode = "delete_mode"
            self.selected_spot = -1
            print("Режим удаления: кликните на место, чтобы удалить его")
        self.update_display()

    def start_clear_all(self):
        """Начинает процесс подтверждения очистки всех мест"""
        if self.spots:
            self.mode = "clear_confirm"
            print("Подтвердите удаление всех мест (Y/N)")
            self.update_display()
        else:
            print("Нет мест для удаления")

    def confirm_clear_all(self):
        """Подтверждает удаление всех мест"""
        if self.mode == "clear_confirm":
            self.spots.clear()
            print("Все места удалены")
            self.mode = "draw"
            self.selected_spot = -1
            self.update_display()

    def cancel_clear_all(self):
        """Отменяет удаление всех мест"""
        if self.mode == "clear_confirm":
            self.mode = "draw"
            print("Удаление отменено")
            self.update_display()

    def toggle_numbers(self):
        """Переключает отображение номеров мест"""
        self.show_numbers = not self.show_numbers
        self.update_display()
        # После переключения номеров окно должно оставаться активным
        # Не сбрасываем режим, просто обновляем отображение

    def reset_mode(self):
        """Сбрасывает текущий режим в режим рисования"""
        self.mode = "draw"
        self.selected_spot = -1
        self.update_display()

    def run(self):
        """Главный цикл приложения"""
        print("\n=== Редактор парковочных мест ===")
        print(f"Видео: {self.video_path}")
        print(f"Файл мест: {self.spots_file}")
        print(f"Загружено мест: {len(self.spots)}")
        print("\nУправление:")
        print("  Мышь: нарисовать прямоугольник (зажать левую кнопку)")
        print("  S: Сохранить")
        print("  Q: Выйти")
        print("  D: Режим удаления (кликнуть на место для удаления)")
        print("  C: Очистить все места (с подтверждением Y/N)")
        print("  R: Сбросить режим")
        print("  H: Показать/скрыть номера мест")
        print("=" * 40)

        self.update_display()

        while True:
            key = cv2.waitKey(1) & 0xFF

            if key == ord('s'):
                # Сохранить
                save_spots(self.spots, self.spots_file)
                self.reset_mode()

            elif key == ord('q'):
                # Выйти
                # if self.spots:
                #     confirm = input("Есть несохранённые изменения. Выйти без сохранения? (y/n): ")
                #     if confirm.lower() == 'y':
                #         break
                # else:
                    break

            elif key == ord('d'):
                # Переключить режим удаления
                self.toggle_delete_mode()

            elif key == ord('c'):
                # Начать очистку всех мест
                self.start_clear_all()

            elif key == ord('r'):
                # Сбросить режим
                self.reset_mode()

            elif key == ord('h'):
                # Переключить отображение номеров
                self.toggle_numbers()

            elif key == ord('y') and self.mode == "clear_confirm":
                # Подтвердить очистку
                self.confirm_clear_all()

            elif key == ord('n') and self.mode == "clear_confirm":
                # Отменить очистку
                self.cancel_clear_all()

            elif key == 27:  # ESC
                # Выход из любого режима в режим рисования
                self.reset_mode()

        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description='Редактор парковочных мест')
    parser.add_argument('--video', type=str, default='vid_frags/video_test.mp4',
                        help='Путь к видеофайлу')
    parser.add_argument('--spots', type=str, default='spots/spots.txt',
                        help='Путь к файлу с координатами мест')

    args = parser.parse_args()

    # Создаём директорию для файла мест, если её нет
    os.makedirs(os.path.dirname(args.spots), exist_ok=True)

    try:
        editor = SpotEditor(args.video, args.spots)
        editor.run()
    except Exception as e:
        print(f"Ошибка: {e}")


if __name__ == "__main__":
    main()