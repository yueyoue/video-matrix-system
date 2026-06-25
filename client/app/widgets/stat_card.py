"""Statistic card widget for dashboard."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from ..styles.theme import PRIMARY


class StatCard(QFrame):
    """A card showing a single statistic with icon, value, label, and optional change."""

    def __init__(self, title: str, value: str = "0", icon: str = "📊",
                 color: str = PRIMARY, change: str = "", parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        self.setStyleSheet(f"QFrame {{ background: white; border: 1px solid #E5E6EB; border-radius: 8px; }}")

        h = QHBoxLayout(self)
        h.setContentsMargins(20, 16, 20, 16)
        h.setSpacing(16)

        # icon
        ic = QLabel(icon)
        ic.setFixedSize(48, 48)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet(f"background: {color}20; border-radius: 24px; font-size: 20px;")
        h.addWidget(ic)

        # text column
        col = QVBoxLayout()
        col.setSpacing(6)

        self._val = QLabel(str(value))
        self._val.setStyleSheet("QLabel { font-size: 24px; font-weight: bold; color: #333; }")
        col.addWidget(self._val)

        row = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet("QLabel { font-size: 12px; color: #999; }")
        row.addWidget(lbl)
        row.addStretch()
        col.addLayout(row)

        h.addLayout(col, 1)

    def set_value(self, value: str):
        self._val.setText(str(value))
