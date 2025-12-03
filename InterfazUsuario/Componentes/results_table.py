from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtGui import QColor

class ResultsTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Archivo", "Estado", "Detalle"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                gridline-color: #f1f3f5;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #dee2e6;
                font-weight: bold;
            }
        """)

    def add_result(self, archivo, estado, detalle):
        row = self.rowCount()
        self.insertRow(row)
        
        item_archivo = QTableWidgetItem(archivo)
        item_estado = QTableWidgetItem(estado)
        item_detalle = QTableWidgetItem(detalle)
        
        # Color coding for status
        if estado == "Correcto" or estado == "Movido" or estado == "Creado":
            item_estado.setForeground(QColor("#28a745")) # Green
        elif estado == "Error" or estado == "Discrepancia":
            item_estado.setForeground(QColor("#dc3545")) # Red
        elif estado == "Omitido":
            item_estado.setForeground(QColor("#ffc107")) # Yellow/Orange
            
        self.setItem(row, 0, item_archivo)
        self.setItem(row, 1, item_estado)
        self.setItem(row, 2, item_detalle)
        
    def clear_results(self):
        self.setRowCount(0)
