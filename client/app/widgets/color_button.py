"""Custom button widgets that bypass Qt stylesheet system entirely."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QPalette
from PyQt6.QtWidgets import QPushButton, QSizePolicy


class ColorButton(QPushButton):
    """Custom-painted button that renders correctly regardless of global stylesheets."""

    def __init__(self, text, bg_color, fg_color="#FFFFFF", hover_color=None, parent=None):
        super().__init__(text, parent)
        self._bg = QColor(bg_color)
        self._fg = QColor(fg_color)
        self._hover = QColor(hover_color or bg_color)
        self._pressed = False
        self._hovered = False
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)
        self.setMinimumWidth(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Disable stylesheet inheritance completely
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        self._pressed = True
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Background
        if self._pressed:
            color = self._bg.darker(120)
        elif self._hovered:
            color = self._hover
        else:
            color = self._bg
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), 4, 4)
        # Text
        p.setPen(self._fg)
        font = self.font()
        font.setPointSize(9)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()

    def sizeHint(self):
        from PyQt6.QtGui import QFontMetrics
        fm = QFontMetrics(self.font())
        w = fm.horizontalAdvance(self.text()) + 24
        return __import__('PyQt6.QtCore', fromlist=['QSize']).QSize(max(w, 50), 28)


def make_delete_btn(text, callback):
    btn = ColorButton(text, "#F53F3F", "#FFFFFF", "#F76965")
    btn.clicked.connect(callback)
    return btn


def make_primary_btn(text, callback):
    btn = ColorButton(text, "#165DFF", "#FFFFFF", "#4080FF")
    btn.clicked.connect(callback)
    return btn


def make_success_btn(text, callback):
    btn = ColorButton(text, "#00B42A", "#FFFFFF", "#23C343")
    btn.clicked.connect(callback)
    return btn


def make_default_btn(text, callback):
    btn = ColorButton(text, "#FFFFFF", "#333333", "#E8F3FF")
    btn.clicked.connect(callback)
    return btn
