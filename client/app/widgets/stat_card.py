"""Statistic card widget for dashboard."""

from PyQt6.QtCore import Qt
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
        self._value_label.setStyleSheet(f"""
            font-size: 28px;
            font-weight: 700;
            color: {TEXT_COLOR};
        """)
        text_layout.addWidget(self._value_label)

        bottom = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 13px; color: {TEXT_SECONDARY};")
        bottom.addWidget(title_label)

        if change:
            change_label = QLabel(change)
            c = SUCCESS if not change.startswith("-") else DANGER
            change_label.setStyleSheet(f"font-size: 12px; color: {c}; font-weight: 500;")
            bottom.addWidget(change_label)

        bottom.addStretch()
        text_layout.addLayout(bottom)
        layout.addLayout(text_layout)
        layout.addStretch()

    def set_value(self, value: str):
        self._value_label.setText(str(value))
