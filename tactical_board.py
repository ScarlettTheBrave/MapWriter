import sys
import math
import time
import pyautogui
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QSlider, QHBoxLayout
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont

pyautogui.PAUSE = 0.001
pyautogui.MINIMUM_SLEEP = 0.001


class DraggableMarker(QLabel):
    def __init__(self, text, shape_type, parent=None):
        super().__init__(text, parent)
        self.shape_type = shape_type
        self.setStyleSheet(
            "background-color: rgba(30, 30, 30, 230); color: #ff5555; padding: 6px; border: 1px solid #ff5555; font-weight: bold;")
        self.setFont(QFont("Consolas", 10))
        self.adjustSize()
        self.offset = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.offset = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            new_pos = self.mapToParent(event.position().toPoint() - self.offset)
            self.move(new_pos)


class OverlayCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.markers = []

    def add_marker(self, text, shape_type):
        marker = DraggableMarker(text, shape_type, self)
        marker.move(self.width() // 2, self.height() // 2)
        marker.show()
        self.markers.append(marker)

    def clear_markers(self):
        for m in self.markers:
            m.deleteLater()
        self.markers.clear()


class ControlPanel(QWidget):
    def __init__(self, canvas):
        super().__init__()
        self.canvas = canvas
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowTitle("Штабной Планшет (Военный)")
        self.setStyleSheet("background-color: #1a1a1a; color: white;")

        layout = QVBoxLayout()

        # Слайдер масштаба
        scale_layout = QHBoxLayout()
        self.scale_label = QLabel("Масштаб: 1.0")
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setMinimum(5)
        self.scale_slider.setMaximum(20)
        self.scale_slider.setValue(10)
        self.scale_slider.valueChanged.connect(self.update_scale_label)
        scale_layout.addWidget(self.scale_label)
        scale_layout.addWidget(self.scale_slider)
        layout.addLayout(scale_layout)

        # Кнопки тактических знаков
        btn_ob = QPushButton("⬛ ОБ (Круг + Крест X)")
        btn_ob.clicked.connect(lambda: self.canvas.add_marker("ОБ [Круг+X]", "ob_circle"))

        btn_pob = QPushButton("▤ ПОБ (Зона + Штриховка)")
        btn_pob.clicked.connect(lambda: self.canvas.add_marker("ПОБ [Штриховка]", "pob_shading"))

        btn_line = QPushButton("⚡ Линия укреплений (Зигзаг)")
        btn_line.clicked.connect(lambda: self.canvas.add_marker("Укрепление", "fort_line"))

        btn_arrow = QPushButton("➔ Направление удара (Стрела)")
        btn_arrow.clicked.connect(lambda: self.canvas.add_marker("Атака", "attack_arrow"))

        btn_draw = QPushButton("▶ ВЫПОЛНИТЬ ПЛАН")
        btn_draw.setStyleSheet("background-color: #b71c1c; font-weight: bold; padding: 12px; margin-top: 10px;")
        btn_draw.clicked.connect(self.execute_plan)

        btn_clear = QPushButton("Очистить холст")
        btn_clear.clicked.connect(self.canvas.clear_markers)

        layout.addWidget(btn_ob)
        layout.addWidget(btn_pob)
        layout.addWidget(btn_line)
        layout.addWidget(btn_arrow)
        layout.addWidget(btn_draw)
        layout.addWidget(btn_clear)
        self.setLayout(layout)

    def update_scale_label(self, value):
        self.scale_label.setText(f"Масштаб: {value / 10.0}")

    def execute_plan(self):
        scale_factor = self.scale_slider.value() / 10.0
        self.canvas.hide()
        self.hide()
        time.sleep(0.5)

        for marker in self.canvas.markers:
            cx = marker.x() + marker.width() // 2
            cy = marker.y() + marker.height() // 2

            if marker.shape_type == "ob_circle":
                draw_ob_marker(cx, cy, radius=int(35 * scale_factor))
            elif marker.shape_type == "pob_shading":
                draw_pob_shading(cx, cy, scale=scale_factor)
            elif marker.shape_type == "fort_line":
                draw_fortification_line(cx, cy, length=int(120 * scale_factor))
            elif marker.shape_type == "attack_arrow":
                draw_attack_arrow(cx - 60, cy, cx + 60, cy)  # Временный вектор по умолчанию

            time.sleep(0.3)

        self.canvas.show()
        self.show()


# --- ВОЕННЫЙ ВЕКТОРНЫЙ ДВИЖОК ---

def draw_smooth_line(x1, y1, x2, y2, steps=10):
    """Плавная линия для точного отклика игры"""
    pyautogui.moveTo(x1, y1)
    pyautogui.mouseDown()
    for i in range(1, steps + 1):
        t = i / steps
        pyautogui.moveTo(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
        time.sleep(0.008)
    pyautogui.mouseUp()
    time.sleep(0.03)


def draw_ob_marker(cx, cy, radius):
    """ОБ: Идеальный круг + вписанный крест X"""
    points = 32
    coords = []
    for i in range(points + 1):
        angle = (2 * math.pi / points) * i
        coords.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))

    # Рисуем окружность
    pyautogui.moveTo(coords[0][0], coords[0][1])
    pyautogui.mouseDown()
    for pt in coords[1:]:
        pyautogui.moveTo(pt[0], pt[1])
        time.sleep(0.006)
    pyautogui.mouseUp()
    time.sleep(0.04)

    # Вписываем крест X (по диагоналям)
    r_diag = radius * 0.707  # Косинус 45 градусов
    draw_smooth_line(cx - r_diag, cy - r_diag, cx + r_diag, cy + r_diag)
    draw_smooth_line(cx - r_diag, cy + r_diag, cx + r_diag, cy - r_diag)


def draw_pob_shading(cx, cy, scale):
    """ПОБ: Прямоугольник с внутренней штриховкой (зачистка/укрепление)"""
    w = int(120 * scale)
    h = int(70 * scale)
    hw, hh = w // 2, h // 2

    x1, y1 = cx - hw, cy - hh
    x2, y2 = cx + hw, cy + hh

    # 1. Периметр
    draw_smooth_line(x1, y1, x2, y1)
    draw_smooth_line(x2, y1, x2, y2)
    draw_smooth_line(x2, y2, x1, y2)
    draw_smooth_line(x1, y2, x1, y1)

    # 2. Военная штриховка внутри (диагональные параллельные линии)
    step = int(15 * scale)
    current_x = x1 + step
    while current_x < x2:
        # Рисуем штрих сверху вниз по диагонали
        draw_smooth_line(current_x, y1, max(x1, current_x - (y2 - y1)), y2, steps=6)
        current_x += step


def draw_fortification_line(cx, cy, length):
    """Линия укреплений (зигзаг / колючая проволока)"""
    half = length // 2
    x1, y1 = cx - half, cy
    x2, y2 = cx + half, cy

    segments = 6
    seg_len = length / segments
    h_tooth = 15  # Высота зубца

    pyautogui.moveTo(x1, y1)
    pyautogui.mouseDown()
    for i in range(segments):
        cur_x = x1 + i * seg_len
        next_x = x1 + (i + 1) * seg_len
        mid_x = cur_x + (seg_len / 2)
        # Зубец вверх-вниз
        pyautogui.moveTo(mid_x, y1 - h_tooth)
        pyautogui.moveTo(next_x, y1)
    pyautogui.mouseUp()
    time.sleep(0.03)


def draw_attack_arrow(x1, y1, x2, y2):
    """Красивая тактическая стрела направления удара"""
    # Стержень стрелы
    draw_smooth_line(x1, y1, x2, y2)

    # Наконечник
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_len = 25

    ax1 = x2 - arrow_len * math.cos(angle - math.pi / 6)
    ay1 = y2 - arrow_len * math.sin(angle - math.pi / 6)
    draw_smooth_line(x2, y2, ax1, ay1)

    ax2 = x2 - arrow_len * math.cos(angle + math.pi / 6)
    ay2 = y2 - arrow_len * math.sin(angle + math.pi / 6)
    draw_smooth_line(x2, y2, ax2, ay2)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    canvas = OverlayCanvas()
    canvas.show()

    panel = ControlPanel(canvas)
    screen_rect = QApplication.primaryScreen().availableGeometry()
    panel.move(screen_rect.width() - 350, 50)
    panel.show()

    sys.exit(app.exec())