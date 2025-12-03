from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt

class ProgressCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 10px;
                border: 1px solid #dee2e6;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-weight: bold; color: #495057; border: none;")
        
        self.lbl_value = QLabel("0 / 0")
        self.lbl_value.setAlignment(Qt.AlignRight)
        self.lbl_value.setStyleSheet("color: #6c757d; border: none;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #e9ecef;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 4px;
            }
        """)
        self.progress_bar.setTextVisible(False)
        
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)
        layout.addWidget(self.progress_bar)

    def update_progress(self, current, total):
        self.lbl_value.setText(f"{current} / {total}")
        if total > 0:
            self.progress_bar.setValue(int((current / total) * 100))
        else:
            self.progress_bar.setValue(0)
