import os
import sys
import math
import time
import ctypes
import traceback
from pathlib import Path

import pyautogui

# ============================================================
# ФУНДАМЕНТАЛЬНЫЙ ФИКС КООРДИНАТ (DPI)
# ============================================================
# Отключаем виртуальное масштабирование Qt.
# Это гарантирует, что координаты клика в приложении
# будут 1:1 совпадать с координатами PyAutoGUI на мониторе.
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"

try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QLabel, QGraphicsItemGroup, QComboBox, QFrame, QGraphicsItem, QMessageBox
)
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPen, QColor, QPainter, QPolygonF, QBrush, QPainterPath


class AbortDrawing(Exception):
    """Вызывается при нажатии Ctrl+C пользователем."""
    pass


# ============================================================
# PYAUTOGUI & ГРАНИЦЫ
# ============================================================
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.0

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "tactical_map_error.log"

# Зоны, за которые курсор физически не имеет права заходить при рисовании
SAFE_MARGIN_TOP = 140
SAFE_MARGIN_BOTTOM = 60
SAFE_MARGIN_LEFT = 30
SAFE_MARGIN_RIGHT = 30


def resource_path(name):
    return str(BASE_DIR / name)


def write_exception_log(prefix, exc):
    text = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {prefix}\n" + "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)) + "\n"
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass


# ============================================================
# ВЕКТОРА ДЛЯ ЦИФР (1-9)
# ============================================================
NUM_VECTORS = {
    "num_1": [(-5, -10), (0, -20), (0, 20)],
    "num_2": [(-10, -20), (10, -20), (10, 0), (-10, 0), (-10, 20), (10, 20)],
    "num_3": [(-10, -20), (10, -20), (10, 0), (-5, 0), (10, 0), (10, 20), (-10, 20)],
    "num_4": [(10, 20), (10, -20), (10, 0), (-10, 0), (-10, -20)],
    "num_5": [(10, -20), (-10, -20), (-10, 0), (10, 0), (10, 20), (-10, 20)],
    "num_6": [(10, -20), (-10, -20), (-10, 20), (10, 20), (10, 0), (-10, 0)],
    "num_7": [(-10, -20), (10, -20), (0, 20)],
    "num_8": [(-10, 0), (-10, -20), (10, -20), (10, 20), (-10, 20), (-10, 0), (10, 0)],
    "num_9": [(10, 0), (-10, 0), (-10, -20), (10, -20), (10, 20), (-10, 20)]
}

# ============================================================
# НАСТРОЙКИ ОТРИСОВКИ (УПРОЩЕННЫЕ И СТРОГИЕ)
# ============================================================
DRAW_SPEED_PIXELS_PER_SEC = 500.0  # Скорость движения мыши (пикс/сек)
DRAW_CORNER_PAUSE = 0.08  # Задержка на вершинах, чтобы сервер "понял" угол
DRAW_START_DELAY = 0.15  # Пауза после зажатия ЛКМ
DRAW_END_DELAY = 0.1  # Пауза после отпускания ЛКМ

COLOR_SWITCH_RETRIES = 3
COLOR_OPEN_DELAY = 0.85
COLOR_CLICK_DELAY = 0.35
COLOR_RETRY_DELAY = 0.30
COLOR_DROPDOWN_IMAGE = resource_path("color_dropdown.png")

# 24 грани для круга - идеальный баланс: выглядит как круг, но не спамит сервер
CIRCLE_POINTS = 24

COLOR_MAP = {
    "Красный": ("red", QColor(244, 67, 54)),
    "Зеленый": ("green", QColor(76, 175, 80)),
    "Синий": ("blue", QColor(33, 150, 243)),
    "Оранжевый": ("orange", QColor(255, 152, 0)),
    "Фиолетовый": ("purple", QColor(156, 39, 176)),
    "Черный": ("black", QColor(40, 40, 40))
}


class DraggableToolbar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_pos = None
        self.setStyleSheet("""
            QFrame { background-color: #1e1e1e; color: #e0e0e0; border-radius: 10px; border: 1px solid #3f3f46; font-family: 'Segoe UI', sans-serif; }
            QPushButton { background-color: #2d2d30; border: 1px solid #3f3f46; padding: 8px; border-radius: 5px; font-weight: 600; }
            QPushButton:hover { background-color: #3e3e42; border: 1px solid #007acc; }
            QPushButton:pressed { background-color: #1c97ea; color: white; }
            QComboBox { background-color: #2d2d30; color: white; padding: 6px; border: 1px solid #3f3f46; border-radius: 4px; }
            QLabel { font-weight: bold; border: none; }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() == Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self.drag_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        super().mouseReleaseEvent(event)


class FrozenBoard(QGraphicsView):
    def __init__(self, main_panel):
        super().__init__()
        self.main_panel = main_panel

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("border: none; background-color: rgba(0, 0, 0, 150);")

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setMouseTracking(True)

        self.current_tool = None
        self.current_angle = 0
        self.current_scale = 1.0
        self.preview_item = None
        self.route_points = []
        self.signs = []

        self.toolbar = DraggableToolbar(self)
        tb_layout = QVBoxLayout(self.toolbar)
        tb_layout.setContentsMargins(15, 15, 15, 15)
        tb_layout.setSpacing(10)

        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Цвет:"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(list(COLOR_MAP.keys()))
        self.color_combo.currentTextChanged.connect(self.update_preview_color)
        color_layout.addWidget(self.color_combo)
        tb_layout.addLayout(color_layout)

        lbl = QLabel("Скролл = Поворот | Shift+Скролл = Масштаб | ПКМ = Завершить маршрут")
        lbl.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: normal; border: none;")
        lbl.setAlignment(Qt.AlignCenter)
        tb_layout.addWidget(lbl)

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(self.make_btn("ОБ (Удар)", "ob"), 0, 0)
        grid.addWidget(self.make_btn("ФОБ (База)", "fob"), 0, 1)
        grid.addWidget(self.make_btn("ПОБ (Зона)", "pob"), 0, 2)
        grid.addWidget(self.make_btn("Стрела", "arrow"), 1, 0)
        grid.addWidget(self.make_btn("Укрепления", "fort_line"), 1, 1)
        grid.addWidget(self.make_btn("Расчистка", "demolition"), 1, 2)
        grid.addWidget(self.make_btn("Изоляция", "no_entry"), 2, 0)
        grid.addWidget(self.make_btn("Маневр", "maneuver"), 2, 1)
        grid.addWidget(self.make_btn("Флаг (Сбор)", "rally"), 2, 2)
        grid.addWidget(self.make_btn("Тактич. зона", "tactical_zone"), 3, 0)
        grid.addWidget(self.make_btn("Внимание!", "hazard"), 3, 1)
        grid.addWidget(self.make_btn("📍 МАРШРУТ", "route"), 3, 2)
        tb_layout.addLayout(grid)

        num_layout = QHBoxLayout()
        num_layout.setSpacing(4)
        for i in range(1, 10):
            btn = self.make_btn(str(i), f"num_{i}")
            btn.setStyleSheet("padding: 6px; font-size: 16px; background-color: #252526;")
            num_layout.addWidget(btn)
        tb_layout.addLayout(num_layout)

        actions_layout = QHBoxLayout()
        btn_draw = QPushButton("▶ НАРИСОВАТЬ В ИГРЕ")
        btn_draw.setStyleSheet("background-color: #d32f2f; color: white; padding: 12px; border: none;")
        btn_draw.clicked.connect(self.execute_plan)
        actions_layout.addWidget(btn_draw)

        btn_cancel = QPushButton("Отмена")
        btn_cancel.setStyleSheet("background-color: #555; padding: 12px; border: none;")
        btn_cancel.clicked.connect(self.cancel_plan)
        actions_layout.addWidget(btn_cancel)

        tb_layout.addLayout(actions_layout)
        self.toolbar.setGeometry(20, 20, 560, 480)

    def make_btn(self, text, tool):
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda: self.set_tool(tool))
        return button

    def update_preview_color(self):
        if self.preview_item and self.current_tool and self.current_tool != "route":
            pos = self.preview_item.pos()
            self.scene.removeItem(self.preview_item)
            self.preview_item = self.create_sign_group(self.current_tool, self.current_scale)
            self.scene.addItem(self.preview_item)
            self.preview_item.setPos(pos)
            self.preview_item.setRotation(self.current_angle)

    def create_sign_group(self, sign_type, scale=1.0, route_pts=None):
        group = QGraphicsItemGroup()
        color_name = self.color_combo.currentText()
        _, qcolor = COLOR_MAP[color_name]
        pen = QPen(qcolor, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        brush = QBrush(qcolor)

        if sign_type == "ob":
            r = 40 * scale
            group.addToGroup(self.scene.addEllipse(-r, -r, r * 2, r * 2, pen))
            r_in = 28 * scale
            group.addToGroup(self.scene.addLine(-r_in, -r_in, r_in, r_in, pen))
            group.addToGroup(self.scene.addLine(-r_in, r_in, r_in, -r_in, pen))
        elif sign_type == "fob":
            w, h = 60 * scale, 40 * scale
            group.addToGroup(self.scene.addRect(-w, -h, w * 2, h * 2, pen))
            group.addToGroup(self.scene.addLine(-w, -h, w, h, pen))
            group.addToGroup(self.scene.addLine(-w, h, w, -h, pen))
        elif sign_type == "pob":
            w, h = 60 * scale, 40 * scale
            group.addToGroup(self.scene.addRect(-w, -h, w * 2, h * 2, pen))
        elif sign_type == "arrow":
            length = 50 * scale
            group.addToGroup(self.scene.addLine(-length, 0, length, 0, pen))
            poly = QPolygonF([QPointF(length, 0), QPointF(length - 20 * scale, -12 * scale),
                              QPointF(length - 20 * scale, 12 * scale)])
            group.addToGroup(self.scene.addPolygon(poly, pen, brush))
        elif sign_type == "maneuver":
            path = QPainterPath()
            path.moveTo(-40 * scale, 40 * scale)
            path.quadTo(0, -60 * scale, 40 * scale, 40 * scale)
            group.addToGroup(self.scene.addPath(path, pen))
            poly = QPolygonF(
                [QPointF(40 * scale, 40 * scale), QPointF(35 * scale, 15 * scale), QPointF(15 * scale, 25 * scale)])
            group.addToGroup(self.scene.addPolygon(poly, pen, brush))
        elif sign_type == "demolition":
            w = 30 * scale
            group.addToGroup(self.scene.addRect(-w, -w, w * 2, w * 2, pen))
            group.addToGroup(self.scene.addLine(-w, 0, 0, -w, pen))
            group.addToGroup(self.scene.addLine(-w, w, w, -w, pen))
            group.addToGroup(self.scene.addLine(0, w, w, 0, pen))
        elif sign_type == "no_entry":
            r = 30 * scale
            group.addToGroup(self.scene.addEllipse(-r, -r, r * 2, r * 2, pen))
            r_in = 21 * scale
            group.addToGroup(self.scene.addLine(-r_in, -r_in, r_in, r_in, pen))
        elif sign_type == "rally":
            pole_len = 45 * scale
            flag_w = 30 * scale
            flag_h = 20 * scale
            group.addToGroup(self.scene.addLine(0, -pole_len, 0, pole_len / 2, pen))
            poly = QPolygonF(
                [QPointF(0, -pole_len), QPointF(flag_w, -pole_len + flag_h / 2), QPointF(0, -pole_len + flag_h)])
            group.addToGroup(self.scene.addPolygon(poly, pen))
        elif sign_type == "fort_line":
            l = 70 * scale
            group.addToGroup(self.scene.addLine(-l, 0, l, 0, pen))
            teeth = 10
            step = (140 * scale) / max(1, (teeth - 1))
            tooth_len = max(8, 15 * scale)
            for i in range(teeth):
                bx = -l + (i * step)
                group.addToGroup(self.scene.addLine(bx, 0, bx, -tooth_len, pen))
        elif sign_type == "tactical_zone":
            r = 45 * scale
            group.addToGroup(self.scene.addEllipse(-r, -r, r * 2, r * 2, pen))
            for i in range(4):
                a = i * math.pi / 2
                x1, y1 = r * math.cos(a), r * math.sin(a)
                x2, y2 = (r - 12 * scale) * math.cos(a), (r - 12 * scale) * math.sin(a)
                group.addToGroup(self.scene.addLine(x1, y1, x2, y2, pen))
        elif sign_type == "hazard":
            s = 40 * scale
            poly = QPolygonF([QPointF(0, -s), QPointF(s * 0.86, s * 0.5), QPointF(-s * 0.86, s * 0.5)])
            group.addToGroup(self.scene.addPolygon(poly, pen))
            group.addToGroup(self.scene.addLine(0, -s * 0.3, 0, s * 0.1, pen))
            group.addToGroup(self.scene.addLine(0, s * 0.25, 0, s * 0.25 + 4, pen))
        elif sign_type.startswith("num_"):
            vecs = NUM_VECTORS[sign_type]
            path = QPainterPath()
            path.moveTo(vecs[0][0] * scale, vecs[0][1] * scale)
            for vx, vy in vecs[1:]:
                path.lineTo(vx * scale, vy * scale)
            group.addToGroup(self.scene.addPath(path, pen))
        elif sign_type == "route" and route_pts:
            path = QPainterPath()
            path.moveTo(0, 0)
            for i in range(1, len(route_pts)):
                dx = route_pts[i].x() - route_pts[0].x()
                dy = route_pts[i].y() - route_pts[0].y()
                path.lineTo(dx, dy)
            group.addToGroup(self.scene.addPath(path, pen))

        return group

    def set_tool(self, tool):
        self.current_tool = tool
        self.current_angle = 0
        self.current_scale = 1.0
        self.route_points = []
        if self.preview_item:
            self.scene.removeItem(self.preview_item)
            self.preview_item = None
        if tool != "route":
            self.preview_item = self.create_sign_group(tool, self.current_scale)
            self.scene.addItem(self.preview_item)
            self.preview_item.hide()
        self.setCursor(Qt.CrossCursor)

    def capture_and_show(self):
        screen = QApplication.primaryScreen()
        pixmap = screen.grabWindow(0)
        self.scene.clear()
        self.signs.clear()
        self.preview_item = None
        self.current_tool = None
        self.setCursor(Qt.ArrowCursor)

        # Гарантируем, что сцена и вид соответствуют 1:1 физическим пикселям
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.setGeometry(0, 0, pixmap.width(), pixmap.height())
        self.scene.addItem(QGraphicsPixmapItem(pixmap))
        self.toolbar.raise_()
        self.showFullScreen()

    def mouseMoveEvent(self, event):
        if self.current_tool and self.current_tool != "route" and self.preview_item:
            pos = self.mapToScene(event.position().toPoint())
            self.preview_item.setPos(pos)
            self.preview_item.setRotation(self.current_angle)
            self.preview_item.show()
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        if self.current_tool:
            modifiers = QApplication.keyboardModifiers()
            delta = 15 if event.angleDelta().y() > 0 else -15
            if modifiers == Qt.ShiftModifier or modifiers == Qt.ControlModifier:
                scale_delta = 0.1 if delta > 0 else -0.1
                self.current_scale = max(0.2, min(4.0, self.current_scale + scale_delta))
            else:
                self.current_angle = (self.current_angle + delta) % 360

            if self.preview_item and self.current_tool != "route":
                pos = self.preview_item.pos()
                self.scene.removeItem(self.preview_item)
                self.preview_item = self.create_sign_group(self.current_tool, self.current_scale)
                self.scene.addItem(self.preview_item)
                self.preview_item.setPos(pos)
                self.preview_item.setRotation(self.current_angle)
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        if self.toolbar.geometry().contains(event.position().toPoint()):
            return super().mousePressEvent(event)

        if not self.current_tool:
            return super().mousePressEvent(event)

        pos = self.mapToScene(event.position().toPoint())
        color_code = COLOR_MAP[self.color_combo.currentText()][0]

        if event.button() == Qt.LeftButton:
            if self.current_tool == "route":
                self.route_points.append(pos)
                self.scene.addEllipse(
                    pos.x() - 4, pos.y() - 4, 8, 8,
                    QPen(QColor(0, 255, 0)), QBrush(QColor(0, 255, 0))
                )
            else:
                placed_item = self.create_sign_group(self.current_tool, self.current_scale)
                placed_item.setFlag(QGraphicsItem.ItemIsMovable)
                self.scene.addItem(placed_item)
                placed_item.setPos(pos)
                placed_item.setRotation(self.current_angle)

                self.signs.append({
                    "id": len(self.signs) + 1, "type": self.current_tool, "item": placed_item,
                    "route": None, "color": color_code, "scale": float(self.current_scale),
                    "done": False, "status": "pending", "error": None
                })
                self.current_tool = None
                if self.preview_item:
                    self.scene.removeItem(self.preview_item)
                    self.preview_item = None
                self.setCursor(Qt.ArrowCursor)

        elif event.button() == Qt.RightButton and self.current_tool == "route":
            if len(self.route_points) > 1:
                placed_item = self.create_sign_group("route", 1.0, self.route_points)
                placed_item.setFlag(QGraphicsItem.ItemIsMovable)
                self.scene.addItem(placed_item)
                placed_item.setPos(self.route_points[0])

                origin = self.route_points[0]
                rel_route = [(pt.x() - origin.x(), pt.y() - origin.y()) for pt in self.route_points]

                self.signs.append({
                    "id": len(self.signs) + 1, "type": "route", "item": placed_item,
                    "route": rel_route, "color": color_code, "scale": 1.0,
                    "done": False, "status": "pending", "error": None
                })
            self.route_points = []
            self.current_tool = None
            self.setCursor(Qt.ArrowCursor)

    def cancel_plan(self):
        self.hide()
        self.main_panel.showNormal()

    def execute_plan(self):
        self.hide()
        pyautogui.mouseUp()
        time.sleep(0.8)
        try:
            self.main_panel.run_pyautogui_macros(self.signs)
        finally:
            pyautogui.mouseUp()
            self.main_panel.showNormal()


class MainPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.last_color = None
        self.setWindowTitle("Тактический планшет v20 (Линейный Движок)")
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.setStyleSheet("""
            QWidget { background-color: #1a1a1a; color: #ffffff; font-family: 'Segoe UI'; }
            QPushButton { background-color: #007acc; border: none; padding: 15px; border-radius: 6px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #1c97ea; }
            QLabel { font-size: 16px; font-weight: bold; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        lbl = QLabel("ТЕРМИНАЛ ГОТОВ")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        btn = QPushButton("📸 ЗАХВАТИТЬ КАРТУ")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.start_planning)
        layout.addWidget(btn)

        self.board = FrozenBoard(self)
        self.queue_status = QLabel("Очередь: 0 | Выполнено: 0 | Цвет: неизвестен")
        self.queue_status.setAlignment(Qt.AlignCenter)
        self.queue_status.setStyleSheet("color: #9ad1ff; font-size: 11px; font-weight: normal;")
        layout.addWidget(self.queue_status)
        self.resize(340, 190)

    def check_abort(self):
        if (ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000) and (
                ctypes.windll.user32.GetAsyncKeyState(0x43) & 0x8000):
            raise AbortDrawing("Отрисовка отменена пользователем (нажато Ctrl+C).")

    def start_planning(self):
        self.showMinimized()
        time.sleep(0.3)
        self.board.capture_and_show()

    def _locate_center(self, image_name, confidence=0.8):
        try:
            return pyautogui.locateCenterOnScreen(image_name, confidence=confidence)
        except Exception:
            return None

    def switch_color_in_game(self, color_code):
        if self.last_color == color_code:
            return True

        print(f"[COLOR] Переключаемся на: {color_code}")

        for attempt in range(1, COLOR_SWITCH_RETRIES + 1):
            self.check_abort()
            pyautogui.mouseUp()

            dropdown_pos = self._locate_center(COLOR_DROPDOWN_IMAGE, confidence=0.72)

            if dropdown_pos:
                pyautogui.moveTo(dropdown_pos.x, dropdown_pos.y, duration=0.18)
                time.sleep(0.1)
                pyautogui.click()
                time.sleep(COLOR_OPEN_DELAY)

                target = self._locate_center(resource_path(f"color_{color_code}.png"), confidence=0.76)
                if target:
                    pyautogui.moveTo(target.x, target.y, duration=0.18)
                    time.sleep(0.1)
                    pyautogui.click()
                    time.sleep(COLOR_CLICK_DELAY)
                    self.last_color = color_code
                    return True

                # Скрываем дропдаун обратно
                pyautogui.moveTo(dropdown_pos.x, dropdown_pos.y, duration=0.1)
                time.sleep(0.1)
                pyautogui.click()
                time.sleep(0.2)

            time.sleep(COLOR_RETRY_DELAY)

        self.last_color = None
        return False

    def _sign_tuple_to_record(self, sign_data):
        if isinstance(sign_data, dict):
            return sign_data
        sign_type, item, route_data, color, scale = sign_data
        return {
            "id": 0, "type": sign_type, "item": item, "route": route_data,
            "color": color, "scale": float(scale), "done": False,
            "status": "pending", "error": None
        }

    def run_pyautogui_macros(self, signs):
        pyautogui.mouseUp()
        self.last_color = None

        total = len(signs)
        completed = sum(1 for raw in signs if self._sign_tuple_to_record(raw).get("done", False))

        self.queue_status.setText(f"Очередь: {total} | Выполнено: {completed}")
        print("=" * 72)
        print("TACTICAL DRAW QUEUE")
        print("Нажмите Ctrl+C для экстренной остановки.")
        print("=" * 72)

        screen_w, screen_h = pyautogui.size()

        try:
            for queue_index, raw in enumerate(signs, start=1):
                self.check_abort()
                record = self._sign_tuple_to_record(raw)

                if record.get("done", False):
                    continue

                sign_type = record["type"]
                item = record["item"]
                route_data = record.get("route")
                color_code = record["color"]
                scale = float(record.get("scale", 1.0))

                record["status"] = "waiting_color"
                record["error"] = None

                if self.last_color != color_code:
                    if not self.switch_color_in_game(color_code):
                        record["status"] = "color_error"
                        record["error"] = f"Цвет {color_code} не найден. Пропуск."
                        print(f"[QUEUE] Ошибка цвета для {sign_type}. Остановка.")
                        break

                        # Ограничиваем координаты центральной точки фигуры экраном
                cx = max(SAFE_MARGIN_LEFT, min(int(round(item.scenePos().x())), screen_w - SAFE_MARGIN_RIGHT))
                cy = max(SAFE_MARGIN_TOP, min(int(round(item.scenePos().y())), screen_h - SAFE_MARGIN_BOTTOM))
                angle = float(item.rotation())

                self.queue_status.setText(f"Рисование: {queue_index}/{total} | {sign_type}")
                QApplication.processEvents()

                record["status"] = "drawing"

                try:
                    if sign_type == "ob":
                        self.draw_game_circle(cx, cy, 40 * scale, angle)
                        r_in = 28 * scale
                        p1 = self.rotate_point(cx - r_in, cy - r_in, cx, cy, angle)
                        p2 = self.rotate_point(cx + r_in, cy + r_in, cx, cy, angle)
                        self.draw_game_continuous_stroke([p1, p2])
                        p3 = self.rotate_point(cx - r_in, cy + r_in, cx, cy, angle)
                        p4 = self.rotate_point(cx + r_in, cy - r_in, cx, cy, angle)
                        self.draw_game_continuous_stroke([p3, p4])

                    elif sign_type == "fob":
                        self.draw_game_fob(cx, cy, 60 * scale, 40 * scale, angle, cross=True)

                    elif sign_type == "pob":
                        self.draw_game_fob(cx, cy, 60 * scale, 40 * scale, angle, cross=False)

                    elif sign_type == "arrow":
                        self.draw_game_arrow(cx, cy, scale, angle)

                    elif sign_type == "maneuver":
                        self.draw_game_maneuver(cx, cy, scale, angle)

                    elif sign_type == "demolition":
                        self.draw_game_demolition(cx, cy, 30 * scale, angle)

                    elif sign_type == "no_entry":
                        self.draw_game_no_entry(cx, cy, 30 * scale, angle)

                    elif sign_type == "rally":
                        self.draw_game_rally(cx, cy, scale, angle)

                    elif sign_type == "fort_line":
                        self.draw_game_fort(cx, cy, scale, angle)

                    elif sign_type == "tactical_zone":
                        self.draw_game_tactical_zone(cx, cy, scale, angle)

                    elif sign_type == "hazard":
                        self.draw_game_hazard(cx, cy, scale, angle)

                    elif sign_type.startswith("num_"):
                        self.draw_game_number(sign_type, cx, cy, scale, angle)

                    elif sign_type == "route":
                        abs_route = [(cx + rx, cy + ry) for rx, ry in route_data]
                        self.draw_game_continuous_stroke(abs_route)

                    record["done"] = True
                    record["status"] = "done"

                except AbortDrawing as exc:
                    raise exc

                except Exception as exc:
                    record["done"] = False
                    record["status"] = "draw_error"
                    record["error"] = repr(exc)
                    print(f"[QUEUE] Ошибка рисования {sign_type}: {exc}")
                    break

                finally:
                    pyautogui.mouseUp()

                time.sleep(0.3)

        except AbortDrawing as exc:
            print(f"[ABORT] {exc}")
            self.queue_status.setText("ОТМЕНЕНО ПОЛЬЗОВАТЕЛЕМ")
            pyautogui.mouseUp()

        pending = sum(1 for raw in signs if not self._sign_tuple_to_record(raw).get("done", False))

        if "ОТМЕНЕНО" not in self.queue_status.text():
            self.queue_status.setText(f"Очередь: {total} | Выполнено: {total - pending}")
        QApplication.processEvents()

    # ========================================================
    # МАТЕМАТИКА И СТРОГАЯ ЛИНЕЙНАЯ ОТРИСОВКА (Без Resample)
    # ========================================================

    def rotate_point(self, px, py, cx, cy, angle_deg):
        rad = math.radians(angle_deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        nx = cx + (px - cx) * cos_a - (py - cy) * sin_a
        ny = cy + (px - cx) * sin_a + (py - cy) * cos_a
        return int(round(nx)), int(round(ny))

    def draw_game_continuous_stroke(self, points):
        """
        Идеальная линейная отрисовка. Никаких микро-точек и сглаживаний.
        Движок SS14 прекрасно проводит прямую линию от клика до отпускания,
        если двигать мышь предсказуемо и с линейным (linear) ускорением.
        """
        if not points or len(points) < 2: return
        screen_w, screen_h = pyautogui.size()

        clamped = []
        for point in points:
            # Двойная защита от кликов по интерфейсу
            x = max(SAFE_MARGIN_LEFT, min(int(round(point[0])), screen_w - SAFE_MARGIN_RIGHT))
            y = max(SAFE_MARGIN_TOP, min(int(round(point[1])), screen_h - SAFE_MARGIN_BOTTOM))
            clamped.append((x, y))

        pyautogui.mouseUp()
        time.sleep(0.05)

        try:
            sx, sy = clamped[0]
            self.check_abort()

            # Подходим к началу без зажатия
            pyautogui.moveTo(sx, sy, duration=0.1, tween=pyautogui.linear)
            time.sleep(0.1)

            pyautogui.mouseDown()
            time.sleep(DRAW_START_DELAY)  # Ждем регистрации сервером начала линии

            prev_x, prev_y = sx, sy
            for x, y in clamped[1:]:
                self.check_abort()

                dist = math.hypot(x - prev_x, y - prev_y)
                if dist < 2:
                    continue  # Фильтруем субпиксельный шум

                # Линейное, плавное движение. Скорость = расстояние / 500 пикселей в сек.
                dur = max(0.02, dist / DRAW_SPEED_PIXELS_PER_SEC)

                pyautogui.moveTo(x, y, duration=dur, tween=pyautogui.linear)
                time.sleep(DRAW_CORNER_PAUSE)  # Обязательная пауза на изломе линии

                prev_x, prev_y = x, y

        finally:
            time.sleep(DRAW_END_DELAY)
            pyautogui.mouseUp()
            time.sleep(0.1)

    # ========================================================
    # ТАКТИЧЕСКИЕ ЭЛЕМЕНТЫ
    # ========================================================

    def draw_game_circle(self, cx, cy, radius, angle):
        coords = []
        for i in range(CIRCLE_POINTS):
            a = (2.0 * math.pi * i / CIRCLE_POINTS)
            coords.append(self.rotate_point(cx + radius * math.cos(a), cy + radius * math.sin(a), cx, cy, angle))
        coords.append(coords[0])
        self.draw_game_continuous_stroke(coords)

    def draw_game_fob(self, cx, cy, hw, hh, angle, cross=False):
        pts = [
            self.rotate_point(cx - hw, cy - hh, cx, cy, angle),
            self.rotate_point(cx + hw, cy - hh, cx, cy, angle),
            self.rotate_point(cx + hw, cy + hh, cx, cy, angle),
            self.rotate_point(cx - hw, cy + hh, cx, cy, angle)
        ]
        self.draw_game_continuous_stroke(pts + [pts[0]])
        if cross:
            self.draw_game_continuous_stroke([pts[0], pts[2]])
            self.draw_game_continuous_stroke([pts[1], pts[3]])

    def draw_game_arrow(self, cx, cy, scale, angle):
        p1 = self.rotate_point(cx - 50 * scale, cy, cx, cy, angle)
        p2 = self.rotate_point(cx + 50 * scale, cy, cx, cy, angle)
        self.draw_game_continuous_stroke([p1, p2])

        line_ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        arr_len = 25 * scale
        arr_ang = math.pi / 6
        h1 = (int(round(p2[0] - arr_len * math.cos(line_ang - arr_ang))),
              int(round(p2[1] - arr_len * math.sin(line_ang - arr_ang))))
        h2 = (int(round(p2[0] - arr_len * math.cos(line_ang + arr_ang))),
              int(round(p2[1] - arr_len * math.sin(line_ang + arr_ang))))
        self.draw_game_continuous_stroke([h1, p2, h2])

    def draw_game_maneuver(self, cx, cy, scale, angle):
        p1 = self.rotate_point(cx - 40 * scale, cy + 40 * scale, cx, cy, angle)
        p_ctrl = self.rotate_point(cx, cy - 60 * scale, cx, cy, angle)
        p2 = self.rotate_point(cx + 40 * scale, cy + 40 * scale, cx, cy, angle)

        steps = max(10, int(20 * scale))
        curve_pts = []
        for i in range(steps + 1):
            t = i / steps
            bx = ((1 - t) ** 2 * p1[0] + 2 * (1 - t) * t * p_ctrl[0] + t ** 2 * p2[0])
            by = ((1 - t) ** 2 * p1[1] + 2 * (1 - t) * t * p_ctrl[1] + t ** 2 * p2[1])
            curve_pts.append((int(round(bx)), int(round(by))))
        self.draw_game_continuous_stroke(curve_pts)

        line_ang = math.atan2(p2[1] - p_ctrl[1], p2[0] - p_ctrl[0])
        arr_len = 20 * scale
        arr_ang = math.pi / 6
        h1 = (int(round(p2[0] - arr_len * math.cos(line_ang - arr_ang))),
              int(round(p2[1] - arr_len * math.sin(line_ang - arr_ang))))
        h2 = (int(round(p2[0] - arr_len * math.cos(line_ang + arr_ang))),
              int(round(p2[1] - arr_len * math.sin(line_ang + arr_ang))))
        self.draw_game_continuous_stroke([h1, p2, h2])

    def draw_game_demolition(self, cx, cy, w, angle):
        pts = [
            self.rotate_point(cx - w, cy - w, cx, cy, angle),
            self.rotate_point(cx + w, cy - w, cx, cy, angle),
            self.rotate_point(cx + w, cy + w, cx, cy, angle),
            self.rotate_point(cx - w, cy + w, cx, cy, angle)
        ]
        self.draw_game_continuous_stroke(pts + [pts[0]])
        self.draw_game_continuous_stroke([
            self.rotate_point(cx - w, cy, cx, cy, angle),
            self.rotate_point(cx, cy - w, cx, cy, angle)
        ])
        self.draw_game_continuous_stroke([
            self.rotate_point(cx - w, cy + w, cx, cy, angle),
            self.rotate_point(cx + w, cy - w, cx, cy, angle)
        ])
        self.draw_game_continuous_stroke([
            self.rotate_point(cx, cy + w, cx, cy, angle),
            self.rotate_point(cx + w, cy, cx, cy, angle)
        ])

    def draw_game_no_entry(self, cx, cy, radius, angle):
        coords = []
        for i in range(CIRCLE_POINTS):
            a = (2.0 * math.pi * i / CIRCLE_POINTS)
            coords.append(self.rotate_point(cx + radius * math.cos(a), cy + radius * math.sin(a), cx, cy, angle))
        coords.append(coords[0])
        self.draw_game_continuous_stroke(coords)
        p1 = self.rotate_point(cx - radius * 0.7, cy - radius * 0.7, cx, cy, angle)
        p2 = self.rotate_point(cx + radius * 0.7, cy + radius * 0.7, cx, cy, angle)
        self.draw_game_continuous_stroke([p1, p2])

    def draw_game_rally(self, cx, cy, scale, angle):
        pole_len = 45 * scale
        flag_w = 30 * scale
        flag_h = 20 * scale

        p1 = self.rotate_point(cx, cy - pole_len, cx, cy, angle)
        p2 = self.rotate_point(cx, cy + pole_len / 2, cx, cy, angle)
        self.draw_game_continuous_stroke([p1, p2])

        f1 = p1
        f2 = self.rotate_point(cx + flag_w, cy - pole_len + flag_h / 2, cx, cy, angle)
        f3 = self.rotate_point(cx, cy - pole_len + flag_h, cx, cy, angle)
        self.draw_game_continuous_stroke([f1, f2, f3, f1])

    def draw_game_fort(self, cx, cy, scale, angle):
        l = max(20, 70 * scale)
        p1 = self.rotate_point(cx - l, cy, cx, cy, angle)
        p2 = self.rotate_point(cx + l, cy, cx, cy, angle)
        self.draw_game_continuous_stroke([p1, p2])

        total_length = 2 * l
        min_spacing = 15
        teeth = max(3, int(total_length / min_spacing) + 1)
        step = total_length / max(1, (teeth - 1))
        tooth_len = max(10, 15 * scale)

        for i in range(teeth):
            bx = cx - l + (i * step)
            base = self.rotate_point(bx, cy, cx, cy, angle)
            tip = self.rotate_point(bx, cy - tooth_len, cx, cy, angle)
            self.draw_game_continuous_stroke([base, tip])

    def draw_game_tactical_zone(self, cx, cy, scale, angle):
        r = max(20, 45 * scale)
        self.draw_game_circle(cx, cy, r, angle)
        tick_len = max(10, 12 * scale)
        for i in range(4):
            a = i * math.pi / 2
            x1 = cx + r * math.cos(a)
            y1 = cy + r * math.sin(a)
            x2 = cx + (r - tick_len) * math.cos(a)
            y2 = cy + (r - tick_len) * math.sin(a)
            p1 = self.rotate_point(x1, y1, cx, cy, angle)
            p2 = self.rotate_point(x2, y2, cx, cy, angle)
            self.draw_game_continuous_stroke([p1, p2])

    def draw_game_hazard(self, cx, cy, scale, angle):
        s = max(20, 40 * scale)
        pts = [
            self.rotate_point(cx, cy - s, cx, cy, angle),
            self.rotate_point(cx + s * 0.86, cy + s * 0.5, cx, cy, angle),
            self.rotate_point(cx - s * 0.86, cy + s * 0.5, cx, cy, angle)
        ]
        self.draw_game_continuous_stroke(pts + [pts[0]])

        p1 = self.rotate_point(cx, cy - s * 0.3, cx, cy, angle)
        p2 = self.rotate_point(cx, cy + s * 0.1, cx, cy, angle)
        self.draw_game_continuous_stroke([p1, p2])

        dot1 = self.rotate_point(cx, cy + s * 0.25, cx, cy, angle)
        dot2 = self.rotate_point(cx, cy + s * 0.25 + max(4, 3 * scale), cx, cy, angle)
        self.draw_game_continuous_stroke([dot1, dot2])

    def draw_game_number(self, num_type, cx, cy, scale, angle):
        vecs = NUM_VECTORS[num_type]
        pts = [self.rotate_point(cx + vx * scale, cy + vy * scale, cx, cy, angle) for vx, vy in vecs]
        self.draw_game_continuous_stroke(pts)


def global_exception_hook(exc_type, exc_value, exc_tb):
    exc = exc_value
    try:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] UNCAUGHT\n{text}\n")
    except Exception:
        pass


sys.excepthook = global_exception_hook

if __name__ == "__main__":
    app = QApplication(sys.argv)
    panel = MainPanel()
    panel.show()
    sys.exit(app.exec())