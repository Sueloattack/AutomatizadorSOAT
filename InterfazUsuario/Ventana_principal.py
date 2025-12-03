# AutomatizadorSOAT/interfaz_usuario/ventana_principal.py
import sys
import os
from pathlib import Path
from PySide6 import QtWidgets, QtCore, QtGui
import traceback

try:
    from Core.trabajador_automatizacion import TrabajadorAutomatizacion
    from Core.trabajador_reporte import TrabajadorReporte
    from Core.utilidades import resource_path
    from Configuracion.constantes import APP_VERSION, CONFIGURACION_AREAS, AREA_GLOSAS_ID, AREA_FACTURACION_ID, MUNDIAL_ESCOLAR_ID
    from Automatizaciones.glosas import mundial_escolar
    
    # Nuevos Módulos
    from Automatizaciones.procesamiento_facturas.repartidor import procesar_reparto
    from Automatizaciones.procesamiento_facturas.revisor import procesar_revision
    from Automatizaciones.procesamiento_facturas.unir_json import procesar_union_json
    
    # Nuevos Componentes UI
    from .Componentes.modern_button import ModernButton
    from .Componentes.progress_card import ProgressCard
    from .Componentes.file_selector import FileSelector
    from .Componentes.results_table import ResultsTable

except ImportError as e:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    QtWidgets.QMessageBox.critical(
        None, "Error de Importación Crítico",
        f"Error importando módulos: {e}\nVerifique los nombres de las carpetas."
    )
    sys.exit(1)

# --- CLASE PARA LA PESTAÑA DE RADICACIÓN (Lógica Original) ---
class TabRadicacion(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent # Referencia a la ventana principal para acceder a atributos globales si es necesario
        self.layout = QtWidgets.QVBoxLayout(self)
        
        self._crear_grupo_seleccion_area()
        self._crear_grupo_seleccion_aseguradora()
        self._crear_grupo_seleccion_carpeta()
        self._crear_botones_accion()
        self._crear_area_log()
        
        self.layout.addWidget(self.grupo_seleccion_area) 
        self.layout.addWidget(self.grupo_seleccion_aseguradora)
        self.layout.addWidget(self.grupo_seleccion_carpeta)
        self.layout.addLayout(self.layout_botones)
        self.layout.addWidget(self.log_label)
        self.layout.addWidget(self.log_text_edit, stretch=1)
        
        # Conexiones
        self.combo_area.currentIndexChanged.connect(self._actualizar_combo_aseguradoras)
        self.browse_button.clicked.connect(self._seleccionar_carpeta)
        self.start_button.clicked.connect(self._iniciar_automatizacion)
        self.report_button.clicked.connect(self._generar_reporte)
        
        # Inicialización
        self._actualizar_combo_aseguradoras()
        self._actualizar_estado_botones(proceso_corriendo=False)

    def _crear_grupo_seleccion_area(self):
        self.grupo_seleccion_area = QtWidgets.QGroupBox("1. Seleccionar Área de Proceso")
        layout = QtWidgets.QVBoxLayout(self.grupo_seleccion_area)
        self.combo_area = QtWidgets.QComboBox()
        self.combo_area.setMinimumHeight(28)
        self.combo_area.addItem("Glosas", userData=AREA_GLOSAS_ID)
        self.combo_area.addItem("Facturación", userData="facturacion")
        layout.addWidget(self.combo_area)

    def _crear_grupo_seleccion_aseguradora(self):
        self.grupo_seleccion_aseguradora = QtWidgets.QGroupBox("2. Seleccionar Aseguradora")
        layout = QtWidgets.QVBoxLayout(self.grupo_seleccion_aseguradora)
        self.combo_aseguradora = QtWidgets.QComboBox()
        self.combo_aseguradora.setMinimumHeight(28)
        layout.addWidget(self.combo_aseguradora)

    def _crear_grupo_seleccion_carpeta(self):
        self.grupo_seleccion_carpeta = QtWidgets.QGroupBox("3. Seleccionar Carpeta Contenedora")
        layout = QtWidgets.QHBoxLayout(self.grupo_seleccion_carpeta)
        self.folder_line_edit = QtWidgets.QLineEdit("...")
        self.folder_line_edit.setReadOnly(True)
        self.folder_line_edit.setMinimumHeight(28)
        layout.addWidget(self.folder_line_edit, stretch=1)
        self.browse_button = QtWidgets.QPushButton("Seleccionar...")
        self.browse_button.setMinimumHeight(28)
        self.browse_button.setFixedWidth(100)
        layout.addWidget(self.browse_button)

    def _crear_botones_accion(self):
        self.layout_botones = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton(" Iniciar Automatización")
        self.start_button.setMinimumHeight(35)
        self.report_button = QtWidgets.QPushButton(" Generar Reporte")
        self.report_button.setMinimumHeight(35)
        self.layout_botones.addStretch(1)
        self.layout_botones.addWidget(self.start_button)
        self.layout_botones.addWidget(self.report_button)
        self.layout_botones.addStretch(1)

    def _crear_area_log(self):
        self.log_label = QtWidgets.QLabel("Log de Proceso:")
        self.log_text_edit = QtWidgets.QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.NoWrap)
        log_font = QtGui.QFont("Consolas", 9) or QtGui.QFont("Courier New", 9)
        self.log_text_edit.setFont(log_font)

    @QtCore.Slot()
    def _actualizar_combo_aseguradoras(self):
        area_actual_id = self.combo_area.currentData()
        self.combo_aseguradora.clear()
        aseguradoras_disponibles = CONFIGURACION_AREAS.get(area_actual_id, [])
        for nombre, id_interno in aseguradoras_disponibles:
            self.combo_aseguradora.addItem(nombre, userData=id_interno)
        self._actualizar_estado_botones(proceso_corriendo=False)

    @QtCore.Slot()
    def _seleccionar_carpeta(self):
        directorio_inicial = self.folder_line_edit.text()
        if not os.path.isdir(directorio_inicial):
            directorio_inicial = os.path.expanduser("~")
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Selecciona CARPETA CONTENEDORA", directorio_inicial
        )
        if folder_path:
            self.folder_line_edit.setText(folder_path)
            if self.main_window.hilo_activo is None or not self.main_window.hilo_activo.isRunning():
                self._actualizar_estado_botones(proceso_corriendo=False)

    @QtCore.Slot()
    def _iniciar_automatizacion(self):
        # Delegamos la lógica de hilos a la ventana principal para mantener la gestión centralizada
        self.main_window.iniciar_automatizacion_radicacion(
            self.combo_area.currentData(),
            self.combo_aseguradora.currentData(),
            self.folder_line_edit.text()
        )

    @QtCore.Slot()
    def _generar_reporte(self):
        self.main_window.iniciar_generacion_reporte(self.folder_line_edit.text())

    def _actualizar_estado_botones(self, proceso_corriendo: bool):
        habilitar = not proceso_corriendo
        folder_path = self.folder_line_edit.text()
        es_valida = os.path.isdir(folder_path) and folder_path != "..."
        
        self.start_button.setEnabled(habilitar and es_valida)
        self.combo_area.setEnabled(habilitar)
        self.combo_aseguradora.setEnabled(habilitar)
        self.browse_button.setEnabled(habilitar)
        
        reporte_ok = False
        if habilitar and es_valida:
            if (Path(folder_path) / "resultados_automatizacion.json").is_file():
                reporte_ok = True
        self.report_button.setEnabled(reporte_ok)

    def append_log(self, msg):
        self.log_text_edit.append(msg)
        self.log_text_edit.verticalScrollBar().setValue(
            self.log_text_edit.verticalScrollBar().maximum()
        )

# --- CLASE PARA LA PESTAÑA DE GESTIÓN DE FACTURAS (NUEVO) ---
class TabGestionFacturas(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        
        # 1. Selector de Carpeta Origen (PDFs)
        self.selector_carpeta = FileSelector("1. Seleccionar carpeta con facturas PDF (Origen)...")
        self.layout.addWidget(self.selector_carpeta)

        # 2. Selector de Carpeta Destino (Raíz Entidades)
        self.selector_carpeta_destino = FileSelector("2. Seleccionar carpeta raíz de Entidades (Destino)...")
        self.layout.addWidget(self.selector_carpeta_destino)
        
        # 3. Tarjetas de Progreso (Placeholder visual)
        self.layout_progreso = QtWidgets.QHBoxLayout()
        self.card_repartidor = ProgressCard("Repartidor")
        self.card_revisor = ProgressCard("Revisor")
        self.layout_progreso.addWidget(self.card_repartidor)
        self.layout_progreso.addWidget(self.card_revisor)
        self.layout.addLayout(self.layout_progreso)
        
        # 4. Botones de Acción (Modernos)
        self.layout_acciones = QtWidgets.QHBoxLayout()
        
        self.btn_repartir = ModernButton("Repartir Facturas", color="#17a2b8", hover_color="#138496")
        self.btn_repartir.clicked.connect(self._ejecutar_repartidor)
        
        self.btn_revisar = ModernButton("Revisar Nomenclatura", color="#ffc107", hover_color="#e0a800")
        self.btn_revisar.clicked.connect(self._ejecutar_revisor)
        
        self.btn_unir_json = ModernButton("Unir JSONs", color="#28a745", hover_color="#218838")
        self.btn_unir_json.clicked.connect(self._ejecutar_union_json)
        
        self.layout_acciones.addWidget(self.btn_repartir)
        self.layout_acciones.addWidget(self.btn_revisar)
        self.layout_acciones.addWidget(self.btn_unir_json)
        self.layout.addLayout(self.layout_acciones)
        
        # 5. Tabla de Resultados
        self.tabla_resultados = ResultsTable()
        self.layout.addWidget(self.tabla_resultados)

    def _validar_carpeta(self, selector):
        path = selector.get_path()
        if not path or not os.path.isdir(path):
            return None
        return path

    def _ejecutar_repartidor(self):
        carpeta_origen = self._validar_carpeta(self.selector_carpeta)
        carpeta_destino = self._validar_carpeta(self.selector_carpeta_destino)
        
        if not carpeta_origen:
            QtWidgets.QMessageBox.warning(self, "Carpeta Origen Inválida", "Seleccione una carpeta de origen válida.")
            return
        if not carpeta_destino:
            QtWidgets.QMessageBox.warning(self, "Carpeta Destino Inválida", "Seleccione una carpeta de destino válida (Raíz Entidades).")
            return
        
        self.tabla_resultados.clear_results()
        # Pasamos ambas carpetas al procesador
        resultados = procesar_reparto(carpeta_origen, carpeta_destino)
        
        for res in resultados:
            self.tabla_resultados.add_result(res["archivo"], res["estado"], res["detalle"])
            
        QtWidgets.QMessageBox.information(self, "Reparto Finalizado", f"Se procesaron {len(resultados)} archivos.")

    def _ejecutar_revisor(self):
        carpeta = self._validar_carpeta(self.selector_carpeta)
        if not carpeta: 
            QtWidgets.QMessageBox.warning(self, "Carpeta Inválida", "Seleccione una carpeta de origen válida.")
            return
        
        self.tabla_resultados.clear_results()
        resultados = procesar_revision(carpeta)
        
        for res in resultados:
            self.tabla_resultados.add_result(res["archivo"], res["estado"], res["detalle"])
            
        QtWidgets.QMessageBox.information(self, "Revisión Finalizada", f"Se revisaron {len(resultados)} archivos.")

    def _ejecutar_union_json(self):
        carpeta = self._validar_carpeta(self.selector_carpeta)
        if not carpeta: 
            QtWidgets.QMessageBox.warning(self, "Carpeta Inválida", "Seleccione una carpeta de origen válida.")
            return
        
        self.tabla_resultados.clear_results()
        resultados = procesar_union_json(carpeta)
        
        for res in resultados:
            self.tabla_resultados.add_result(res["archivo"], res["estado"], res["detalle"])
            
        QtWidgets.QMessageBox.information(self, "Unión Finalizada", f"Proceso completado.")


class VentanaPrincipal(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.headless_activo = True
        self.dark_theme_str = ""
        self.light_theme_str = ""
        self.theme_mode = 'light' 
        
        try:
            dark_theme_path = resource_path("InterfazUsuario/dark_theme.qss")
            with open(dark_theme_path, "r") as f: self.dark_theme_str = f.read()
            light_theme_path = resource_path("InterfazUsuario/light_theme.qss")
            with open(light_theme_path, "r") as f: self.light_theme_str = f.read()
            self.setStyleSheet(self.light_theme_str)
        except FileNotFoundError:
            print("ADVERTENCIA: No se encontró tema.")
        
        self.hilo_activo = None
        self.worker_activo = None
        self.app_icon = None

        self.setWindowTitle(f"Automatizador SOAT Glosas v{APP_VERSION}")
        self.setGeometry(100, 100, 800, 750) # Un poco más ancho para las tablas

        self.ruta_icono_png = "Recursos/Icons/pingu.png"
        self.app_icon = self._cargar_icono_app(self.ruta_icono_png)
        if self.app_icon and not self.app_icon.isNull():
            self.setWindowIcon(self.app_icon)

        self._crear_icono_bandeja()

        # --- LAYOUT PRINCIPAL ---
        self.main_layout = QtWidgets.QVBoxLayout(self)
        
        self._crear_titulo()
        self.main_layout.addLayout(self.titulo_layout)
        
        # --- PESTAÑAS ---
        self.tabs = QtWidgets.QTabWidget()
        self.tab_radicacion = TabRadicacion(self)
        self.tab_gestion = TabGestionFacturas(self)
        
        self.tabs.addTab(self.tab_radicacion, "Radicación")
        self.tabs.addTab(self.tab_gestion, "Gestión Facturas")
        
        self.main_layout.addWidget(self.tabs)

        if self.tray_icon and QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()

    # --- MÉTODOS DELEGADOS PARA RADICACIÓN ---
    def iniciar_automatizacion_radicacion(self, area_id, aseguradora_id, folder_path):
        if self.hilo_activo and self.hilo_activo.isRunning():
            QtWidgets.QMessageBox.warning(self, "Proceso Activo", "Ya hay un proceso en curso.")
            return

        if not aseguradora_id or not folder_path or not os.path.isdir(folder_path):
            QtWidgets.QMessageBox.warning(self, "Entrada Inválida", "Seleccione aseguradora y carpeta válida.")
            return

        self.tab_radicacion.log_text_edit.clear()
        self.tab_radicacion.append_log(f"Preparando automatización...")
        self.tab_radicacion._actualizar_estado_botones(proceso_corriendo=True)
        # Desactivar botones globales también
        self.headless_button.setEnabled(False)
        self.theme_button.setEnabled(False)

        self.hilo_activo = QtCore.QThread(self)
        self.worker_activo = TrabajadorAutomatizacion(area_id, aseguradora_id, folder_path, self.headless_activo)
        self.worker_activo.moveToThread(self.hilo_activo)

        self.worker_activo.progreso_update.connect(self.tab_radicacion.append_log)
        self.worker_activo.finalizado.connect(self._manejar_finalizacion_worker)
        self.worker_activo.error_critico.connect(self._mostrar_error_critico)
        self.hilo_activo.finished.connect(self.worker_activo.deleteLater)
        self.hilo_activo.finished.connect(self.hilo_activo.deleteLater)
        self.hilo_activo.finished.connect(self._limpiar_referencias_post_hilo)
        self.hilo_activo.started.connect(self.worker_activo.run_automation)
        self.hilo_activo.start()

    def iniciar_generacion_reporte(self, folder_path):
        # Similar logic for report generation...
        if self.hilo_activo and self.hilo_activo.isRunning(): return
        
        ruta_json = Path(folder_path) / "resultados_automatizacion.json"
        if not ruta_json.is_file():
            QtWidgets.QMessageBox.warning(self, "Error", "No hay resultados para reportar.")
            return

        self.tab_radicacion.append_log(f"Generando reporte...")
        self.tab_radicacion._actualizar_estado_botones(proceso_corriendo=True)
        self.headless_button.setEnabled(False)
        self.theme_button.setEnabled(False)

        self.hilo_activo = QtCore.QThread(self)
        self.worker_activo = TrabajadorReporte(folder_path)
        self.worker_activo.moveToThread(self.hilo_activo)

        self.worker_activo.progreso_update.connect(self.tab_radicacion.append_log)
        self.worker_activo.finalizado.connect(self._manejar_finalizacion_worker)
        self.worker_activo.error_critico.connect(self._mostrar_error_critico)
        self.hilo_activo.finished.connect(self.worker_activo.deleteLater)
        self.hilo_activo.finished.connect(self.hilo_activo.deleteLater)
        self.hilo_activo.finished.connect(self._limpiar_referencias_post_hilo)
        self.hilo_activo.started.connect(self.worker_activo.run_report_generation)
        self.hilo_activo.start()

    # --- MÉTODOS COMPARTIDOS / HEREDADOS ---
    def _cargar_icono_app(self, ruta_relativa_icono):
        # (Mismo código que antes)
        try:
            icon_path = resource_path(ruta_relativa_icono)
            if os.path.exists(icon_path):
                return QtGui.QIcon(icon_path)
        except: pass
        return None

    def _crear_icono_bandeja(self):
        # (Mismo código simplificado)
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable(): return
        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        if self.app_icon: self.tray_icon.setIcon(self.app_icon)
        else: self.tray_icon.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon))
        
        tray_menu = QtWidgets.QMenu(self)
        tray_menu.addAction("Mostrar Ventana", self._mostrar_ventana_desde_bandeja)
        tray_menu.addAction("Salir", self._salir_aplicacion)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._icono_bandeja_activado)

    def _crear_titulo(self):
        self.titulo_layout = QtWidgets.QHBoxLayout()
        self.titulo_layout.setContentsMargins(10, 5, 10, 15)
        
        icon_lbl = QtWidgets.QLabel()
        if self.app_icon: icon_lbl.setPixmap(self.app_icon.pixmap(32, 32))
        
        title_lbl = QtWidgets.QLabel(f"Automatizador SOAT v{APP_VERSION}")
        title_lbl.setFont(QtGui.QFont("Segoe UI", 16, QtGui.QFont.Weight.Bold))
        
        self.headless_button = QtWidgets.QPushButton("🙈")
        self.headless_button.setFixedSize(32, 32)
        self.headless_button.clicked.connect(self._toggle_headless_mode)
        
        self.theme_button = QtWidgets.QPushButton("🌙")
        self.theme_button.setFixedSize(32, 32)
        self.theme_button.clicked.connect(self._toggle_theme)

        self.titulo_layout.addWidget(icon_lbl)
        self.titulo_layout.addStretch()
        self.titulo_layout.addWidget(title_lbl)
        self.titulo_layout.addStretch()
        self.titulo_layout.addWidget(self.headless_button)
        self.titulo_layout.addWidget(self.theme_button)

    @QtCore.Slot()
    def _toggle_headless_mode(self):
        self.headless_activo = not self.headless_activo
        self.headless_button.setText("🙈" if self.headless_activo else "👁️")

    @QtCore.Slot()
    def _toggle_theme(self):
        if self.theme_mode == 'light':
            self.setStyleSheet(self.dark_theme_str)
            self.theme_button.setText("☀️")
            self.theme_mode = 'dark'
        else:
            self.setStyleSheet(self.light_theme_str)
            self.theme_button.setText("🌙")
            self.theme_mode = 'light'

    @QtCore.Slot()
    def _manejar_finalizacion_worker(self, *args):
        # Lógica simplificada de finalización
        self.tab_radicacion._actualizar_estado_botones(proceso_corriendo=False)
        self.headless_button.setEnabled(True)
        self.theme_button.setEnabled(True)
        
        # Mostrar popup (reutilizar lógica existente si es necesario, aquí simplificado)
        if len(args) >= 2:
            QtWidgets.QMessageBox.information(self, "Proceso Finalizado", "La tarea ha terminado.")
        
        if self.hilo_activo: self.hilo_activo.quit()

    @QtCore.Slot(str)
    def _mostrar_error_critico(self, mensaje):
        self.tab_radicacion.append_log(f"ERROR: {mensaje}")
        QtWidgets.QMessageBox.critical(self, "Error Crítico", mensaje)
        self.tab_radicacion._actualizar_estado_botones(proceso_corriendo=False)
        self.headless_button.setEnabled(True)
        self.theme_button.setEnabled(True)
        if self.hilo_activo: self.hilo_activo.quit()

    @QtCore.Slot()
    def _limpiar_referencias_post_hilo(self):
        self.hilo_activo = None
        self.worker_activo = None
        self.tab_radicacion._actualizar_estado_botones(proceso_corriendo=False)
        self.headless_button.setEnabled(True)
        self.theme_button.setEnabled(True)

    @QtCore.Slot(QtWidgets.QSystemTrayIcon.ActivationReason)
    def _icono_bandeja_activado(self, reason):
        if reason in (QtWidgets.QSystemTrayIcon.ActivationReason.Trigger, QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick):
            self._mostrar_ventana_desde_bandeja()

    def _mostrar_ventana_desde_bandeja(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _salir_aplicacion(self):
        if self.hilo_activo and self.hilo_activo.isRunning():
            if QtWidgets.QMessageBox.warning(self, "Salir", "Proceso activo. ¿Salir?", QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No) == QtWidgets.QMessageBox.StandardButton.No:
                return
        if self.tray_icon: self.tray_icon.hide()
        QtWidgets.QApplication.instance().quit()

    def closeEvent(self, event):
        if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable() and self.tray_icon:
            self.hide()
            self.tray_icon.show()
            self.tray_icon.showMessage("Minimizado", "La aplicación sigue ejecutándose.", self.tray_icon.icon(), 2000)
            event.ignore()
        else:
            event.accept()

