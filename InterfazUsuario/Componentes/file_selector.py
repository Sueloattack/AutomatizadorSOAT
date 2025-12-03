from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QFileDialog
from .modern_button import ModernButton

class FileSelector(QWidget):
    def __init__(self, placeholder="Seleccionar carpeta...", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText(placeholder)
        self.path_input.setReadOnly(True)
        self.path_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ced4da;
                border-radius: 6px;
                padding: 8px;
                background-color: #ffffff;
            }
        """)
        
        self.btn_browse = ModernButton("Examinar", color="#6c757d", hover_color="#5a6268")
        self.btn_browse.clicked.connect(self._select_folder)
        
        layout.addWidget(self.path_input)
        layout.addWidget(self.btn_browse)
        
    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        if folder:
            self.path_input.setText(folder)

    def get_path(self):
        return self.path_input.text()
