import pyautogui
import keyboard
import time
import random
import math

# --- НАСТРОЙКИ ---
BASE_SPEED = 0.08  # Базовая скорость протягивания
BASE_PAUSE = 0.1  # Базовая пауза
SCALE = 1.0  # Глобальный масштаб

# --- СКРИНШОТЫ КНОПОК ИНТЕРФЕЙСА ---
BTN_LINES = "Screenshot 2026-08-19 142319.png"
BTN_RESET = "Screenshot 2026-08-19 142236.png"

# Глобальная переменная для умных маршрутов
route_start = None

# --- БАЗА ВЕКТОРОВ (На сетке 50x80) ---
PATTERNS = {
    "П": [(0, 80, 0, 0), (0, 0, 40, 0), (40, 0, 40, 80)],
    "О": [(0, 0, 40, 0), (40, 0, 40, 80), (40, 80, 0, 80), (0, 80, 0, 0)],
    "Б": [(0, 80, 0, 0), (0, 0, 40, 0), (0, 40, 40, 40), (40, 40, 40, 80), (40, 80, 0, 80)]
}


def human_sleep():
    """Плавающая задержка для обхода анти-спама"""
    time.sleep(random.uniform(BASE_PAUSE, BASE_PAUSE + 0.08))


def get_jitter():
    """Микро-дрожание координат для 'человечности'"""
    return random.uniform(-2, 2)


def click_ui_button(image_name):
    """Ищет кнопку на экране и кликает по ней"""
    anchor_x, anchor_y = pyautogui.position()
    try:
        btn_location = pyautogui.locateCenterOnScreen(image_name, confidence=0.8)
        if btn_location:
            pyautogui.moveTo(btn_location.x, btn_location.y, duration=0.1)
            pyautogui.click()
            time.sleep(0.1)
            pyautogui.moveTo(anchor_x, anchor_y, duration=0.1)  # Возврат курсора
            return True
        return False
    except Exception as e:
        print(f"Кнопка не найдена: {e}")
        return False


def draw_line(start_x, start_y, end_x, end_y):
    """Рисует один отрезок с рандомизацией"""
    sx = start_x + get_jitter()
    sy = start_y + get_jitter()
    ex = end_x + get_jitter()
    ey = end_y + get_jitter()

    speed = random.uniform(BASE_SPEED, BASE_SPEED + 0.05)

    pyautogui.moveTo(sx, sy)
    pyautogui.mouseDown()
    pyautogui.moveTo(ex, ey, duration=speed)
    pyautogui.mouseUp()
    human_sleep()


# --- ТАКТИЧЕСКИЕ ФИГУРЫ ---

def draw_circle_ob(radius=40):
    """Рисует идеальный круг для Опорной Базы"""
    if not click_ui_button(BTN_LINES): return

    anchor_x, anchor_y = pyautogui.position()
    segments = 12
    points = []

    for i in range(segments + 1):
        angle = (2 * math.pi / segments) * i
        x = anchor_x + (radius * SCALE) * math.cos(angle)
        y = anchor_y + (radius * SCALE) * math.sin(angle)
        points.append((x, y))

    print("Рисую зону ОБ...")
    for i in range(len(points) - 1):
        draw_line(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])
    print("ОБ завершена!")


def draw_text_internal(word, start_x, start_y, text_scale):
    """Внутренняя функция для печати слов (используется внутри ПОБ)"""
    offset_x = 0
    for char in word.upper():
        lines = PATTERNS.get(char)
        if lines:
            for line in lines:
                dx1, dy1, dx2, dy2 = line
                draw_line(
                    start_x + offset_x + (dx1 * text_scale),
                    start_y + (dy1 * text_scale),
                    start_x + offset_x + (dx2 * text_scale),
                    start_y + (dy2 * text_scale)
                )
            offset_x += 50 * text_scale  # Отступ до следующей буквы


def draw_pob(width=120, height=80):
    """Рисует зону Передовой Опорной Базы с надписью ПОБ внутри"""
    if not click_ui_button(BTN_LINES): return

    anchor_x, anchor_y = pyautogui.position()
    w = width * SCALE
    h = height * SCALE

    print("Рисую периметр ПОБ...")
    # Чертим прямоугольник
    draw_line(anchor_x, anchor_y, anchor_x + w, anchor_y)
    draw_line(anchor_x + w, anchor_y, anchor_x + w, anchor_y + h)
    draw_line(anchor_x + w, anchor_y + h, anchor_x, anchor_y + h)
    draw_line(anchor_x, anchor_y + h, anchor_x, anchor_y)

    print("Вписываю текст ПОБ...")
    # Высчитываем координаты для текста внутри (примерно по центру)
    text_scale = SCALE * 0.4
    text_start_x = anchor_x + (w * 0.15)
    text_start_y = anchor_y + (h * 0.25)

    draw_text_internal("ПОБ", text_start_x, text_start_y, text_scale)
    print("ПОБ возведена!")


def draw_route():
    """Умная стрелка маршрута. Требует двух нажатий: старт и финиш."""
    global route_start
    if route_start is None:
        route_start = pyautogui.position()
        print("Старт маршрута задан! Наведи курсор на конец и нажми хоткей еще раз.")
    else:
        end_x, end_y = pyautogui.position()
        start_x, start_y = route_start
        route_start = None  # Сбрасываем для следующих маршрутов

        if not click_ui_button(BTN_LINES): return

        print("Прокладываю маршрут...")
        # Основная линия
        draw_line(start_x, start_y, end_x, end_y)

        # Математика для наконечника стрелы
        angle = math.atan2(end_y - start_y, end_x - start_x)
        arrow_len = 20 * SCALE

        # Левое перо
        lw_x = end_x - arrow_len * math.cos(angle - math.pi / 6)
        lw_y = end_y - arrow_len * math.sin(angle - math.pi / 6)
        draw_line(end_x, end_y, lw_x, lw_y)

        # Правое перо
        rw_x = end_x - arrow_len * math.cos(angle + math.pi / 6)
        rw_y = end_y - arrow_len * math.sin(angle + math.pi / 6)
        draw_line(end_x, end_y, rw_x, rw_y)
        print("Маршрут проложен!")


def reset_map():
    click_ui_button(BTN_RESET)
    print("Масштаб карты сброшен.")


# --- УПРАВЛЕНИЕ ---
print("--- ТАКТИЧЕСКАЯ КОНСОЛЬ v3 ---")
print(" F4 - ОБ (Круг)")
print(" F5 - ПОБ (Прямоугольник + текст)")
print(" F6 - Умный Маршрут (Нажать на старте,    затем нажать на финише)")
print(" F7 - Сбросить масштаб карты")
print("Esc - Выход")

keyboard.add_hotkey('F4', draw_circle_ob)
keyboard.add_hotkey('F5', draw_pob)
keyboard.add_hotkey('F6', draw_route)
keyboard.add_hotkey('F7', reset_map)

keyboard.wait('esc')