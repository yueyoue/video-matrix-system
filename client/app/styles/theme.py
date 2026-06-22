"""UI Theme & Style definitions for the video matrix system."""

# ── Color Palette ──────────────────────────────────────────────
PRIMARY = "#165DFF"
PRIMARY_HOVER = "#4080FF"
PRIMARY_PRESSED = "#0E42D2"
SUCCESS = "#00B42A"
WARNING = "#FF7D00"
DANGER = "#F53F3F"
DANGER_HOVER = "#F76965"
BG_COLOR = "#F5F7FA"
BORDER_COLOR = "#E5E6EB"
TEXT_COLOR = "#333333"
TEXT_SECONDARY = "#999999"
WHITE = "#FFFFFF"
SIDEBAR_BG = "#FFFFFF"
SIDEBAR_WIDTH = 240
HEADER_HEIGHT = 56

# ── Button Styles ──────────────────────────────────────────────
BTN_PRIMARY = f"""
    QPushButton {{
        background: {PRIMARY};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background: {PRIMARY_HOVER};
    }}
    QPushButton:pressed {{
        background: {PRIMARY_PRESSED};
    }}
    QPushButton:disabled {{
        background: #C9CDD4;
    }}
"""

BTN_PRIMARY_SM = f"""
    QPushButton {{
        background: {PRIMARY};
        color: white;
        border: none;
        border-radius: 4px;
        padding: 4px 12px;
        font-size: 12px;
    }}
    QPushButton:hover {{ background: {PRIMARY_HOVER}; }}
    QPushButton:disabled {{ background: #C9CDD4; }}
"""

BTN_DEFAULT = f"""
    QPushButton {{
        background: white;
        color: {TEXT_COLOR};
        border: 1px solid {BORDER_COLOR};
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
    }}
    QPushButton:hover {{
        border-color: {PRIMARY};
        color: {PRIMARY};
    }}
"""

BTN_DANGER = f"""
    QPushButton {{
        background: {DANGER};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
    }}
    QPushButton:hover {{ background: {DANGER_HOVER}; }}
"""

BTN_SUCCESS = f"""
    QPushButton {{
        background: {SUCCESS};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
    }}
    QPushButton:hover {{ background: #23C343; }}
"""

BTN_TEXT = f"""
    QPushButton {{
        background: transparent;
        color: {PRIMARY};
        border: none;
        padding: 4px 8px;
        font-size: 13px;
    }}
    QPushButton:hover {{ color: {PRIMARY_HOVER}; }}
"""

BTN_DANGER_TEXT = f"""
    QPushButton {{
        background: transparent;
        color: {DANGER};
        border: none;
        padding: 4px 8px;
        font-size: 13px;
    }}
    QPushButton:hover {{ color: {DANGER_HOVER}; }}
"""

# ── Input Styles ───────────────────────────────────────────────
INPUT_STYLE = f"""
    QLineEdit, QComboBox {{
        border: 1px solid {BORDER_COLOR};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
        color: {TEXT_COLOR};
        background: white;
    }}
    QLineEdit:focus, QComboBox:focus {{
        border-color: {PRIMARY};
    }}
    QLineEdit::placeholder {{
        color: {TEXT_SECONDARY};
    }}
"""

TEXTAREA_STYLE = f"""
    QTextEdit {{
        border: 1px solid {BORDER_COLOR};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
        color: {TEXT_COLOR};
        background: white;
    }}
    QTextEdit:focus {{
        border-color: {PRIMARY};
    }}
"""

SPINBOX_STYLE = f"""
    QSpinBox {{
        border: 1px solid {BORDER_COLOR};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
        color: {TEXT_COLOR};
        background: white;
    }}
"""

SLIDER_STYLE = f"""
    QSlider::groove:horizontal {{
        border: none;
        height: 6px;
        background: {BORDER_COLOR};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {PRIMARY};
        border: none;
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }}
    QSlider::sub-page:horizontal {{
        background: {PRIMARY};
        border-radius: 3px;
    }}
"""

CHECKBOX_STYLE = f"""
    QCheckBox {{
        font-size: 13px;
        color: {TEXT_COLOR};
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {BORDER_COLOR};
        border-radius: 3px;
        background: white;
    }}
    QCheckBox::indicator:checked {{
        background: {PRIMARY};
        border-color: {PRIMARY};
    }}
"""

# ── Table Styles ───────────────────────────────────────────────
TABLE_STYLE = f"""
    QTableWidget {{
        background: white;
        border: 1px solid {BORDER_COLOR};
        border-radius: 8px;
        gridline-color: {BORDER_COLOR};
        font-size: 13px;
        color: {TEXT_COLOR};
    }}
    QTableWidget::item {{
        padding: 8px 12px;
        border-bottom: 1px solid {BORDER_COLOR};
    }}
    QTableWidget::item:selected {{
        background: #E8F3FF;
        color: {PRIMARY};
    }}
    QHeaderView::section {{
        background: #F9F9F9;
        font-weight: bold;
        border: none;
        border-bottom: 1px solid {BORDER_COLOR};
        padding: 10px 12px;
        font-size: 13px;
        color: {TEXT_COLOR};
    }}
"""

# ── Card Styles ────────────────────────────────────────────────
CARD_STYLE = f"""
    background: white;
    border: 1px solid {BORDER_COLOR};
    border-radius: 8px;
"""

CARD_STYLE_WITH_SHADOW = f"""
    background: white;
    border: 1px solid {BORDER_COLOR};
    border-radius: 8px;
"""

# ── Dialog Styles ──────────────────────────────────────────────
DIALOG_STYLE = f"""
    QDialog {{
        background: {BG_COLOR};
    }}
"""

# ── Tab Widget ─────────────────────────────────────────────────
TAB_STYLE = f"""
    QTabWidget::pane {{
        border: none;
        background: {BG_COLOR};
    }}
    QTabBar::tab {{
        background: transparent;
        color: {TEXT_SECONDARY};
        padding: 8px 20px;
        font-size: 14px;
        border: none;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{
        color: {PRIMARY};
        border-bottom: 2px solid {PRIMARY};
    }}
    QTabBar::tab:hover {{
        color: {PRIMARY};
    }}
"""

# ── Scrollbar ──────────────────────────────────────────────────
SCROLLBAR_STYLE = """
    QScrollBar:vertical {
        border: none;
        background: transparent;
        width: 6px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #C9CDD4;
        border-radius: 3px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: #A0A4AB;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
"""

# ── Progress Bar ───────────────────────────────────────────────
PROGRESS_STYLE = f"""
    QProgressBar {{
        border: none;
        background: {BORDER_COLOR};
        border-radius: 4px;
        height: 8px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: {PRIMARY};
        border-radius: 4px;
    }}
"""

# ── Global App Stylesheet ──────────────────────────────────────
GLOBAL_STYLESHEET = f"""
    * {{
        font-family: "Microsoft YaHei", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    }}
    QMainWindow {{
        background: {BG_COLOR};
    }}
    QWidget {{
        font-size: 13px;
        color: {TEXT_COLOR};
    }}
    {SCROLLBAR_STYLE}
"""
