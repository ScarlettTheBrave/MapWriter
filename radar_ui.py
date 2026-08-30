import sys
import pymem
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtCore import QTimer, Qt


# ==========================================
# ЧТЕНИЕ ПАМЯТИ
# ==========================================
def read_dotnet_string(pm, address, max_length=100):
    if address == 0: return None
    try:
        length = pm.read_int(address + 0x08)
        if length <= 0 or length > max_length: return None
        return pm.read_bytes(address + 0x0C, length * 2).decode('utf-16le')
    except Exception:
        return None


def get_radar_data(pm, base_addr):
    marines, xenos, structures = [], [], []
    try:
        blips_ptr = pm.read_longlong(base_addr + 0x18)
        if blips_ptr == 0: return marines, xenos, structures

        entries_ptr = pm.read_longlong(blips_ptr + 0x10)
        raw_count = pm.read_int(blips_ptr + 0x38)  # Наши победные оффсеты!

        for i in range(raw_count):
            entry_base = entries_ptr + 0x10 + (i * 0x40)
            uid = pm.read_int(entry_base + 0x08)
            if uid <= 0: continue

            x = pm.read_int(entry_base + 0x28)
            y = pm.read_int(entry_base + 0x2C)

            ptr_icon = pm.read_longlong(entry_base + 0x10)
            ptr_bg = pm.read_longlong(entry_base + 0x18)

            icon = read_dotnet_string(pm, pm.read_longlong(ptr_icon + 0x08)) if ptr_icon else "null"
            bg = read_dotnet_string(pm, pm.read_longlong(ptr_bg + 0x08)) if ptr_bg else "null"

            # Эвристика
            if icon in ["generator", "sensor_tower", "supply"]:
                structures.append((x, y))
            elif bg and ("cbrn" in bg or "squad" in bg or "background" in bg):
                marines.append((x, y))
            elif icon in ["engi", "medic", "marine", "leader"]:
                marines.append((x, y))
            elif icon in ["runner", "drone", "queen", "xeno"]:
                xenos.append((x, y))

    except Exception:
        pass  # Игнорируем ошибки, чтобы UI не падал

    return marines, xenos, structures


# ==========================================
# ИНТЕРФЕЙС PYSIDE6
# ==========================================
class RadarOverlay(QWidget):
    def __init__(self, pm, base_addr):
        super().__init__()
        self.pm = pm
        self.base_addr = base_addr

        self.marines = []
        self.xenos = []
        self.structures = []

        self.initUI()

        # Таймер обновления радара (каждые 500 мс)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(500)

    def initUI(self):
        self.setWindowTitle('RMC-14 Live Radar')
        self.resize(800, 800)
        # Темно-серый хакерский фон
        self.setStyleSheet("background-color: #121212;")
        self.show()

    def update_data(self):
        self.marines, self.xenos, self.structures = get_radar_data(self.pm, self.base_addr)
        self.update()  # Вызывает paintEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Центр экрана (координаты 0,0 в игре)
        cx = self.width() // 2
        cy = self.height() // 2

        # Масштаб карты (можно крутить колесиком потом, пока хардкод)
        scale = 2.0

        # Рисуем сетку перекрестия
        painter.setPen(QPen(QColor("#333333"), 1, Qt.DashLine))
        painter.drawLine(cx, 0, cx, self.height())
        painter.drawLine(0, cy, self.width(), cy)

        def draw_blips(blips, color, size, is_rect=False):
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.NoPen)
            for x, y in blips:
                # В SS14 ось Y обычно инвертирована относительно UI
                screen_x = cx + (x * scale)
                screen_y = cy - (y * scale)

                if is_rect:
                    painter.drawRect(int(screen_x - size / 2), int(screen_y - size / 2), size, size)
                else:
                    painter.drawEllipse(int(screen_x - size / 2), int(screen_y - size / 2), size, size)

        # Рисуем Структуры (Серые квадраты)
        draw_blips(self.structures, "#888888", 8, is_rect=True)

        # Рисуем Морпехов (Синие круги)
        draw_blips(self.marines, "#00aaff", 10, is_rect=False)

        # Рисуем Ксеносов (Красные круги)
        draw_blips(self.xenos, "#ff3333", 10, is_rect=False)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    try:
        pm = pymem.Pymem("Content.Client.exe")
    except pymem.exception.ProcessNotFound:
        print("Ошибка: игра не запущена.")
        sys.exit()

    # НАШ ПОБЕДНЫЙ АДРЕС
    BASE_ADDR = 0x227fe10f0f0

    overlay = RadarOverlay(pm, BASE_ADDR)
    sys.exit(app.exec())