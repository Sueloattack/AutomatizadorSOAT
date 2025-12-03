from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QColor, QPalette

class ModernButton(QPushButton):
    def __init__(self, text, color="#007bff", hover_color="#0056b3", parent=None):
        super().__init__(text, parent)
        self.default_color = color
        self.hover_color = hover_color
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.default_color};
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {self.hover_color};
            }}
            QPushButton:pressed {{
                background-color: {self.darker_color(self.default_color)};
            }}
        """)

    def darker_color(self, hex_color):
        # Simple logic to darken color for pressed state
        return hex_color # Placeholder, CSS handles hover well enough usually

from PySide6.QtCore import Qt
