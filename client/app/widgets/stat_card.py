"""Statistic card widget for dashboard."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from ..styles.theme import (
    CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, SUCCESS, WARNING, DANGER
)


class StatCard(QFrame):
    """A card showing a single statistic with icon, value, label, and optional change."""

    def __init__(self, title: str, value: str = "0", icon: str = "📊",
                 color: str = PRIMARY, change: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                {CARD_STYLE}
                padding: 20px;
            }}
            QFrame:hover {{
                border-color: {color};
            }}
        """)
        self.setFixedHeight(120)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # icon circle
        icon_label = QLabel(icon)
        icon_label.setFixedSize(48, 48)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background: {color}18;
            border-radius: 24px;
            font-size: 22px;
        """)
        layout.addWidget(icon_label)

        # text area
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        self._value_label = QLabel(str(value))
        value_font = QFont()
        value_font.setPointSize(20)
        value_font.setBold(True)
        self._value_label.setFont(value_font)
        self._value_label.setStyleSheet(f"color: {TEXT_COLOR}; background: transparent;")
        self._value_label.setMinimumWidth(60)
        text_layout.addWidget(self._value_label)

        bottom = QHBoxLayout()
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(10)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        bottom.addWidget(title_label)

        if change:
            change_label = QLabel(change)
            c = SUCCESS if not change.startswith("-") else DANGER
            change_font = QFont()
            change_font.setPointSize(9)
            change_label.setFont(change_font)
            change_label.setStyleSheet(f"color: {c}; background: transparent;")
            bottom.addWidget(change_label)

        bottom.addStretch()
        text_layout.addLayout(bottom)
        layout.addLayout(text_layout)
        layout.addStretch()

    def set_value(self, value: str):
        self._value_label.setText(str(value))
