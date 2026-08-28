import cv2
import os

IMAGE_PATH = "marines.png"
OUTPUT_DIR = "extracted_icons"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

image = cv2.imread(IMAGE_PATH)
if image is None:
    print(f"ОШИБКА: Не могу найти '{IMAGE_PATH}'.")
    exit()

print("ИНСТРУКЦИЯ:")
print("1. Выдели иконку мышкой прямо в открывшемся окне.")
print("2. Нажми ENTER или ПРОБЕЛ.")
print("3. Переключись в консоль, введи название (например, t3_boiler) и нажми Enter.")
print("4. Повтори для остальных. Чтобы выйти - выдели пустоту и нажми Enter (или нажми ESC).")

while True:
    # Открывает окно, где ты сам рисуешь квадрат мышкой
    roi = cv2.selectROI("Interactive Cropper (Press ESC to exit)", image, showCrosshair=True, fromCenter=False)
    x, y, w, h = roi

    # Если ничего не выделили или нажали ESC - выходим
    if w == 0 or h == 0:
        break

    icon = image[y:y + h, x:x + w]

    # Окно может перекрывать терминал, так что переключись в него
    name = input("Введи название иконки (без .png): ")
    if not name:
        name = f"icon_{x}_{y}"  # Заглушка, если нажал Enter без текста

    file_path = os.path.join(OUTPUT_DIR, f"{name}.png")
    cv2.imwrite(file_path, icon)
    print(f" [+] Сохранено: {name}.png\n")

cv2.destroyAllWindows()