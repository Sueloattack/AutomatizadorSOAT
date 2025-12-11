"""
Diálogo de resultados modernizado con soporte para dark mode.
Muestra resultados estructurados de la automatización.
"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QTableWidget, QTableWidgetItem, QPushButton,
                               QTabWidget, QWidget, QHeaderView, QApplication)
from PySide6.QtCore import Qt, QDesktopServices, QUrl
from PySide6.QtGui import QClipboard
from pathlib import Path


class CopyableTableWidget(QTableWidget):
    """TableWidget con capacidad de copiar al portapapeles."""
    
    def keyPressEvent(self, event):
        if event.matches(QApplication.StandardKey.Copy):
            self.copy_selection()
        else:
            super().keyPressEvent(event)
    
    def copy_selection(self):
        selection = self.selectedRanges()
        if not selection:
            return
        
        rows = []
        for r in range(selection[0].topRow(), selection[0].bottomRow() + 1):
            cols = []
            for c in range(selection[0].leftColumn(), selection[0].rightColumn() + 1):
                item = self.item(r, c)
                cols.append(item.text() if item else "")
            rows.append("\t".join(cols))
        
        QApplication.clipboard().setText("\n".join(rows))


class ResultsDialog(QDialog):
    """
    Diálogo modernizado para mostrar resultados de automatización.
    Diseño coincidente con versión legacy: contadores grandes, iconos y tema oscuro.
    """
    
    def __init__(self, exitosos, fallos, omitidos, carpeta_base, parent=None):
        super().__init__(parent)
        self.exitosos = exitosos
        self.fallos = fallos
        self.omitidos = omitidos
        self.carpeta_base = Path(carpeta_base) if carpeta_base else None
        
        # Calcular total
        self.total = len(exitosos) + len(fallos) + len(omitidos)
        
        self.setWindowTitle("Proceso Finalizado")
        self.resize(1000, 650)
        self.setup_ui()
    
    def setup_ui(self):
        # Fondo principal oscuro
        self.setStyleSheet("background-color: #1e1e1e; color: #e0e0e0;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # --- ENCABEZADO Y ESTADÍSTICAS ---
        header_layout = QHBoxLayout()
        
        # Título a la izquierda
        title = QLabel("Proceso Finalizado")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Estadísticas a la derecha (Total, Exitos, Fallos, Omitidos)
        # Colores del screenshot: Azul (Total), Verde (Exitos), Rojo (Fallos), Amarillo/Naranja (Omitidos)
        self._add_stat(header_layout, "Total", self.total, "#2196F3")
        self._add_stat(header_layout, "Éxitos", len(self.exitosos), "#4CAF50")
        self._add_stat(header_layout, "Fallos", len(self.fallos), "#F44336")
        self._add_stat(header_layout, "Omitidos", len(self.omitidos), "#FFC107")
        
        main_layout.addLayout(header_layout)
        
        # --- TABS ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #333; background: #252526; }
            QTabBar::tab { background: #2d2d30; color: #aaa; padding: 10px 15px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
            QTabBar::tab:selected { background: #3e3e42; color: white; border-top: 2px solid #4CAF50; }
            QTabBar::tab:hover:!selected { background: #333; }
        """)
        
        # Iconos (Unicode simulation for simplicity and reliability)
        # Tab Exitosos (Verde)
        tab_exitos = self._create_table_tab("exitosos")
        self.tabs.addTab(tab_exitos, f"✅ Éxitos ({len(self.exitosos)})")
        
        # Tab Fallos (Rojo)
        tab_fallos = self._create_table_tab("fallos")
        self.tabs.addTab(tab_fallos, f"❌ Fallos ({len(self.fallos)})")
        
        # Tab Omitidos (Amarillo)
        tab_omitidos = self._create_table_tab("omitidos")
        self.tabs.addTab(tab_omitidos, f"⚠️ Omitidos ({len(self.omitidos)})")
        
        # Seleccionar el tab con más contenido o el primero relevante
        if self.fallos: self.tabs.setCurrentIndex(1)
        elif self.omitidos: self.tabs.setCurrentIndex(2)
        else: self.tabs.setCurrentIndex(0)
            
        main_layout.addWidget(self.tabs)
        
        # --- BOTONES DEL PIE ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setCursor(Qt.PointingHandCursor)
        btn_cerrar.setStyleSheet("""
            QPushButton { background-color: #333; color: white; border: 1px solid #555; padding: 8px 16px; border-radius: 4px; }
            QPushButton:hover { background-color: #444; border-color: #777; }
        """)
        btn_cerrar.clicked.connect(self.accept)
        btn_layout.addWidget(btn_cerrar)
        
        main_layout.addLayout(btn_layout)
        
        # Cargar datos
        self.tables = {"exitosos": tab_exitos, "fallos": tab_fallos, "omitidos": tab_omitidos}
        self._load_tables()
    
    def _add_stat(self, layout, label, value, color):
        """Agrega una estadística estilo dashboard (número grande arriba, label abajo)."""
        container = QWidget()
        v_layout = QVBoxLayout(container)
        v_layout.setContentsMargins(15, 0, 15, 0)
        v_layout.setSpacing(5)
        
        # Número grande
        lbl_val = QLabel(str(value))
        lbl_val.setAlignment(Qt.AlignCenter)
        lbl_val.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {color}; background: transparent;")
        
        # Etiqueta pequeña
        lbl_txt = QLabel(label)
        lbl_txt.setAlignment(Qt.AlignCenter)
        lbl_txt.setStyleSheet("font-size: 11px; color: #888; font-weight: normal; background: transparent;")
        
        v_layout.addWidget(lbl_val)
        v_layout.addWidget(lbl_txt)
        layout.addWidget(container)
    
    def _create_table_tab(self, category):
        """Crea la tabla con el estilo oscuro."""
        table = CopyableTableWidget()
        table.setColumnCount(3)
        cols = ["Referencia", "Resultado", "Detalle"]
        table.setHorizontalHeaderLabels(cols)
        
        # Estilo de tabla oscuro
        table.setStyleSheet("""
            QTableWidget { background-color: #252526; color: #ddd; border: none; gridline-color: #333; }
            QHeaderView::section { background-color: #333; color: #eee; padding: 8px; border: none; font-weight: bold; }
            QTableWidget::item { padding: 5px; border-bottom: 1px solid #2d2d30; }
            QTableWidget::item:selected { background-color: #094771; }
        """)
        
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        table.setColumnWidth(2, 60) # Ancho fijo para icono carpeta
        
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        
        return table
    
    def _load_tables(self):
        """Carga datos en las tablas."""
        # Helper para procesar items
        def add_item_to_table(table, item, tipo):
            row = table.rowCount()
            table.insertRow(row)
            
            ref = "N/A"
            res = "Desconocido"
            path = ""
            log = ""
            
            if isinstance(item, dict):
                ref = item.get('referencia', 'N/A')
                path = item.get('ruta', '')
                log = item.get('log', '')
                if tipo == 'exito':
                    res = f"Radicado: {item.get('radicado', 'N/A')}"
                elif tipo == 'fallo':
                    res = item.get('error', 'Error')
                elif tipo == 'omitido':
                    res = f"Omitido ({item.get('motivo', '')})"
            else:
                s = str(item)
                ref = s.split(':')[0] if ':' in s else s[:20]
                res = s
            
            # Col 0: Referencia
            table.setItem(row, 0, QTableWidgetItem(ref))
            
            # Col 1: Resultado
            table.setItem(row, 1, QTableWidgetItem(res))
            
            # Col 2: Botón Carpeta (Icono)
            # Usamos un botón con icono unicode de carpeta 📁
            if path:
                btn = QPushButton("📁")
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet("""
                    QPushButton { background: transparent; border: none; font-size: 16px; color: #FFC107; }
                    QPushButton:hover { color: #FFE082; }
                """)
                # Usar lambda con valor por defecto para capturar variable
                btn.clicked.connect(lambda kept_path=path: self._abrir_ruta(kept_path))
                table.setCellWidget(row, 2, btn)
            else:
                table.setItem(row, 2, QTableWidgetItem(""))

        # Llenar tablas
        for i in self.exitosos: add_item_to_table(self.tables["exitosos"], i, 'exito')
        for i in self.fallos: add_item_to_table(self.tables["fallos"], i, 'fallo')
        for i in self.omitidos: add_item_to_table(self.tables["omitidos"], i, 'omitido')

    def _abrir_ruta(self, path_str):
        if path_str and Path(path_str).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(path_str))
