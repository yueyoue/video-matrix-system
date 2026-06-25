"""Toast notification widget."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint
from PyQt6.QtWidgets import QLabel, QWidget, QHBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtGui import QColor, QPainter, QPainterPath

from ..styles.theme import SUCCESS, DANGER, WARNING, PRIMARY


class Toast(QLabel):
    """Floating toast notification that auto-dismisses."""

    _instances: list["Toast"] = []

    def __init__(self, message: str, parent: QWidget, level: str = "info",
                 duration: int = 2500):
        super().__init__(parent)
        Toast._instances.append(self)

        colors = {
            "success": (SUCCESS, "✓"),
            "error": (DANGER, "✕"),
            "warning": (WARNING, "⚠"),
            "info": (PRIMARY, "ℹ"),
        }
        color, icon = colors.get(level, colors["info"])

        self.setText(f"  {icon}  {message}")
        self.setWordWrap(True)
        self.setStyleSheet(f"""
            QLabel {{
                background: {color};
                color: white;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
            }}
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedWidth(min(400, parent.width() - 40))
        self.adjustSize()

        # position at top-center of parent
        x = (parent.width() - self.width()) // 2
        self.move(x, 20)
        self.show()
        self.raise_()

        # fade-in opacity
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

        QTimer.singleShot(duration, self._dismiss)

    def _dismiss(self):
        self.hide()
        if self in Toast._instances:
            Toast._instances.remove(self)
        self.deleteLater()

    @classmethod
    def show_message(cls, parent: QWidget, message: str, level: str = "info",
                     duration: int = 2500):
        return cls(message, parent, level, duration)

    @classmethod
    def success(cls, parent: QWidget, message: str):
        return cls.show_message(parent, message, "success")

    @classmethod
    def error(cls, parent: QWidget, message: str):
        return cls.show_message(parent, message, "error", 3500)

    @classmethod
    def warning(cls, parent: QWidget, message: str):
        return cls.show_message(parent, message, "warning")

    @classmethod
    def info(cls, parent: QWidget, message: str):
        return cls.show_message(parent, message, "info")
