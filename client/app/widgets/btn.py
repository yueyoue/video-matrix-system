"""Simple cell button helper - no custom classes, just plain QPushButton."""

from PyQt6.QtWidgets import QPushButton, QSizePolicy


def cell_btn(text, bg, fg, hover_bg, callback):
    """Create a table cell button with inline stylesheet."""
    btn = QPushButton(text)
    btn.setCursor(__import__('PyQt6.QtCore', fromlist=['Qt']).Qt.CursorShape.PointingHandCursor)
    btn.setFixedSize(80, 28)
    btn.setStyleSheet(
        f"QPushButton {{background:{bg};color:{fg};border:none;border-radius:4px;font-size:12px;font-weight:bold;}}"
        f"QPushButton:hover {{background:{hover_bg};}}"
    )
    btn.clicked.connect(callback)
    btn.show()
    return btn


def btn_delete(text, callback):
    return cell_btn(text, "#F53F3F", "#FFFFFF", "#F76965", callback)

def btn_primary(text, callback):
    return cell_btn(text, "#165DFF", "#FFFFFF", "#4080FF", callback)

def btn_success(text, callback):
    return cell_btn(text, "#00B42A", "#FFFFFF", "#23C343", callback)

def btn_default(text, callback):
    return cell_btn(text, "#FFFFFF", "#333333", "#E8F3FF", callback)


def top_btn(text, bg, fg, hover_bg, callback):
    """Top action bar button - slightly larger."""
    btn = QPushButton(text)
    btn.setCursor(__import__('PyQt6.QtCore', fromlist=['Qt']).Qt.CursorShape.PointingHandCursor)
    btn.setFixedSize(120, 34)
    btn.setStyleSheet(
        f"QPushButton {{background:{bg};color:{fg};border:none;border-radius:6px;font-size:13px;font-weight:bold;}}"
        f"QPushButton:hover {{background:{hover_bg};}}"
    )
    btn.clicked.connect(callback)
    btn.show()
    return btn
