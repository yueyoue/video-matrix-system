#!/usr/bin/env python3
"""Video Matrix System - Desktop Client Entry Point."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QStackedWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from app.styles.theme import GLOBAL_STYLESHEET
from app.auth import auth
from app.views.login import LoginView
from app.views.main_window import MainWindow


class AppController:
    """Controls navigation between login and main window."""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setStyleSheet(GLOBAL_STYLESHEET)

        # set default font
        font = QFont("Microsoft YaHei", 10)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        self.app.setFont(font)

        # stacked widget to switch between login and main
        self._stack = QStackedWidget()
        self._stack.setWindowTitle("矩阵运营系统")
        self._stack.setMinimumSize(1200, 800)

        # login view
        self._login_view = LoginView()
        self._login_view.login_success.connect(self._show_main)

        # main window
        self._main_window = MainWindow()
        self._main_window.logout_signal.connect(self._show_login)

        self._stack.addWidget(self._login_view)
        self._stack.addWidget(self._main_window)

    def run(self):
        if auth.is_valid:
            self._show_main()
        else:
            self._show_login()

        self._stack.resize(1400, 900)
        self._stack.show()
        return self.app.exec()

    def _show_main(self):
        self._main_window._load_user_info()
        self._main_window._on_menu_changed("dashboard")
        self._stack.setCurrentIndex(1)
        self._stack.setWindowTitle("矩阵运营系统")
        self._stack.resize(1400, 900)

    def _show_login(self):
        self._stack.setCurrentIndex(0)
        self._stack.setWindowTitle("矩阵运营系统 - 登录")
        self._stack.resize(420, 520)


def main():
    controller = AppController()
    sys.exit(controller.run())


if __name__ == "__main__":
    main()
