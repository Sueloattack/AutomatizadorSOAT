# AutomatizadorSOAT/interfaz_usuario/ventana_principal.py
import sys
import os
from pathlib import Path
from PySide6 import QtWidgets, QtCore, QtGui
import traceback

# Importar trabajadores y constantes
# ¡¡ASEGÚRATE QUE LOS NOMBRES 'nucleo' y 'configuracion' coincidan con tus carpetas!!
try:
    from Core.trabajador_automatizacion import TrabajadorAutomatizacion
    from Core.trabajador_reporte import TrabajadorReporte
    from Core.utilidades import resource_path  # Importar resource_path
    from Configuracion.constantes import APP_VERSION, ASEGURADORAS_CONFIG
except ImportError as e:
    # Mostrar un error crítico si no se pueden importar los módulos principales
    app = (
        QtWidgets.QApplication.instance()
    )  # Obtener instancia existente o crearla si no existe
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    msg_box = QtWidgets.QMessageBox()
    msg_box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
    msg_box.setWindowTitle("Error de Importación Crítico")
    msg_box.setText(
        f"Error importando módulos: {e}\nVerifique nombres/rutas de carpetas (nucleo, configuracion)."
    )
    msg_box.exec()
    sys.exit(1)


class VentanaPrincipal(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # --- Inicialización de Atributos ---
        self.hilo_activo = None
        self.worker_activo = None
        self.app_icon = None  # Inicializar icono

        # --- Configuración Ventana ---
        self.setWindowTitle(f"Automatizador SOAT Glosas v{APP_VERSION}")
        self.setGeometry(100, 100, 650, 600)

        # --- Cargar Icono ---
        self.ruta_icono_png = "Recursos/Icons/pingu.png"  # Ruta al PNG
        self.app_icon = self._cargar_icono_app(self.ruta_icono_png)
        if self.app_icon and not self.app_icon.isNull():
            self.setWindowIcon(
                self.app_icon
            )  # Establecer icono para ventana/barra tareas
            print(f"DEBUG: Icono de ventana establecido desde {self.ruta_icono_png}")
        else:
            print("ADVERTENCIA: No se pudo cargar o es nulo el icono para la ventana.")

        # --- Crear Icono de Bandeja y Menú ---
        # Se llama aquí para inicializar self.tray_icon ANTES de usarlo al final de __init__
        self._crear_icono_bandeja()

        # --- Layout Principal ---
        self.main_layout = QtWidgets.QVBoxLayout(self)

        # --- Crear Widgets y Layouts ---
        self._crear_titulo()
        self._crear_grupo_seleccion_aseguradora()
        self._crear_grupo_seleccion_carpeta()
        self._crear_botones_accion()
        self._crear_area_log()

        # --- Añadir Widgets y Layouts al Principal ---
        self.main_layout.addLayout(self.titulo_layout)
        self.main_layout.addWidget(self.grupo_seleccion_aseguradora)
        self.main_layout.addWidget(self.grupo_seleccion_carpeta)
        self.main_layout.addLayout(self.layout_botones)
        self.main_layout.addWidget(self.log_label)
        self.main_layout.addWidget(self.log_text_edit, stretch=1)

        # --- Conectar Señales de Widgets UI ---
        self.browse_button.clicked.connect(self._seleccionar_carpeta)
        self.start_button.clicked.connect(self._iniciar_automatizacion)
        self.report_button.clicked.connect(self._generar_reporte)

        # --- Estado inicial de botones ---
        self._actualizar_estado_botones(proceso_corriendo=False)

        # --- MOSTRAR ICONO DE BANDEJA AL INICIO ---
        if self.tray_icon and QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()
            print("DEBUG: Icono de bandeja mostrado al inicio.")
        elif not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            print("ADVERTENCIA: Bandeja del sistema no disponible.")
        # -----------------------------------------

    def _cargar_icono_app(self, ruta_relativa_icono) -> QtGui.QIcon | None:
        """Carga un icono desde la carpeta de recursos."""
        try:
            icon_path = resource_path(ruta_relativa_icono)
            print(f"DEBUG: Intentando cargar icono desde: {icon_path}")
            if os.path.exists(icon_path):
                icon = QtGui.QIcon(icon_path)
                if not icon.isNull():
                    print(
                        f"DEBUG: Icono '{ruta_relativa_icono}' cargado correctamente."
                    )
                    return icon
                else:
                    print(
                        f"ADVERTENCIA: QIcon está nulo después de cargar desde {icon_path}. ¿Formato inválido?"
                    )
                    return None
            else:
                print(f"ADVERTENCIA: Archivo de icono no encontrado en {icon_path}")
                return None
        except Exception as e:
            print(f"ERROR al cargar el icono '{ruta_relativa_icono}': {e}")
            traceback.print_exc()
            return None

    def _crear_icono_bandeja(self):
        """Crea el QSystemTrayIcon y su menú."""
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            print("ADVERTENCIA: Bandeja del sistema no disponible, no se creará icono.")
            self.tray_icon = None  # Importante para comprobaciones posteriores
            return

        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        # Usar el icono PNG cargado (self.app_icon), o fallback si falló
        tray_icon_image = (
            self.app_icon if self.app_icon and not self.app_icon.isNull() else None
        )
        if tray_icon_image is None:
            print(
                "ADVERTENCIA: Icono para bandeja es nulo, usando icono estándar del sistema."
            )
            style = self.style() or QtWidgets.QApplication.style()
            std_icon = style.standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon
            )
            self.tray_icon.setIcon(std_icon)
        else:
            self.tray_icon.setIcon(tray_icon_image)

        self.tray_icon.setToolTip("Automatizador SOAT Glosas")

        tray_menu = QtWidgets.QMenu(self)
        mostrar_action = QtGui.QAction(
            "Mostrar Ventana", self, triggered=self._mostrar_ventana_desde_bandeja
        )
        salir_action = QtGui.QAction("Salir", self, triggered=self._salir_aplicacion)
        tray_menu.addAction(mostrar_action)
        tray_menu.addSeparator()
        tray_menu.addAction(salir_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._icono_bandeja_activado)
        # Se mostrará explícitamente al final de __init__ o en closeEvent

    def _crear_titulo(self):
        """Crea el título grande CON ICONO."""
        self.titulo_layout = QtWidgets.QHBoxLayout()
        self.titulo_layout.setContentsMargins(10, 5, 10, 15)  # Margen general

        # Etiqueta para el icono
        self.icono_titulo_label = QtWidgets.QLabel()
        if self.app_icon and not self.app_icon.isNull():
            pixmap = self.app_icon.pixmap(QtCore.QSize(32, 32))  # Ajusta tamaño
            self.icono_titulo_label.setPixmap(pixmap)
        else:
            # Si no hay icono, dejar un espacio vacío del mismo tamaño
            self.icono_titulo_label.setFixedSize(32, 32)

        # Etiqueta para el texto
        self.titulo_texto_label = QtWidgets.QLabel(
            f"Automatizador SOAT Glosas v{APP_VERSION}"
        )
        font = QtGui.QFont("Segoe UI", 16, QtGui.QFont.Weight.Bold)  # Usar fuente común
        self.titulo_texto_label.setFont(font)

        # Añadir icono, texto y stretch para centrar texto
        self.titulo_layout.addWidget(
            self.icono_titulo_label,
            0,
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter,
        )
        self.titulo_layout.addStretch(1)  # Empuja el texto al centro
        self.titulo_layout.addWidget(
            self.titulo_texto_label, 0, QtCore.Qt.AlignmentFlag.AlignCenter
        )
        self.titulo_layout.addStretch(1)  # Empuja desde la derecha

    def _crear_grupo_seleccion_aseguradora(self):
        """Crea el GroupBox para selección de aseguradora."""
        self.grupo_seleccion_aseguradora = QtWidgets.QGroupBox(
            "1. Seleccionar Aseguradora"
        )
        layout = QtWidgets.QVBoxLayout(self.grupo_seleccion_aseguradora)
        self.combo_aseguradora = QtWidgets.QComboBox()
        self.combo_aseguradora.setMinimumHeight(28)
        for nombre, id_interno in ASEGURADORAS_CONFIG:
            self.combo_aseguradora.addItem(nombre, userData=id_interno)
        layout.addWidget(self.combo_aseguradora)

    def _crear_grupo_seleccion_carpeta(self):
        """Crea el GroupBox para selección de carpeta."""
        self.grupo_seleccion_carpeta = QtWidgets.QGroupBox(
            "2. Seleccionar Carpeta Contenedora"
        )
        layout = QtWidgets.QHBoxLayout(self.grupo_seleccion_carpeta)
        self.folder_line_edit = QtWidgets.QLineEdit("...")
        self.folder_line_edit.setReadOnly(True)
        self.folder_line_edit.setMinimumHeight(28)
        layout.addWidget(self.folder_line_edit, stretch=1)  # Permitir que se expanda
        self.browse_button = QtWidgets.QPushButton("Seleccionar...")
        self.browse_button.setMinimumHeight(28)
        self.browse_button.setFixedWidth(100)  # Ancho fijo
        layout.addWidget(self.browse_button)

    def _crear_botones_accion(self):
        """Crea los botones de acción."""
        self.layout_botones = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton(" Iniciar Automatización")
        self.start_button.setMinimumHeight(35)
        self.report_button = QtWidgets.QPushButton(" Generar Reporte")
        self.report_button.setMinimumHeight(35)
        self.layout_botones.addStretch(1)  # Espacio a la izquierda
        self.layout_botones.addWidget(self.start_button)
        self.layout_botones.addWidget(self.report_button)
        self.layout_botones.addStretch(1)  # Espacio a la derecha

    def _crear_area_log(self):
        """Crea el área de log."""
        self.log_label = QtWidgets.QLabel("Log de Proceso:")
        self.log_text_edit = QtWidgets.QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.NoWrap)
        log_font = QtGui.QFont("Consolas", 9) or QtGui.QFont("Courier New", 9)
        self.log_text_edit.setFont(log_font)

    # --- Slots (Respuesta a eventos UI) ---

    @QtCore.Slot()
    def _seleccionar_carpeta(self):
        """Abre diálogo para seleccionar carpeta y actualiza estado botones."""
        directorio_inicial = self.folder_line_edit.text()
        if not os.path.isdir(directorio_inicial):
            directorio_inicial = os.path.expanduser("~")
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Selecciona CARPETA CONTENEDORA", directorio_inicial
        )
        if folder_path:
            self.folder_line_edit.setText(folder_path)
            if self.hilo_activo is None or not self.hilo_activo.isRunning():
                self._actualizar_estado_botones(proceso_corriendo=False)

    @QtCore.Slot()
    def _iniciar_automatizacion(self):
        """Inicia el proceso de automatización."""
        if self.hilo_activo and self.hilo_activo.isRunning():
            QtWidgets.QMessageBox.warning(
                self, "Proceso Activo", "Ya hay un proceso en curso."
            )
            return
        aseguradora_id = self.combo_aseguradora.currentData()
        folder_path = self.folder_line_edit.text()
        if (
            not aseguradora_id
            or not folder_path
            or folder_path == "..."
            or not os.path.isdir(folder_path)
        ):
            QtWidgets.QMessageBox.warning(
                self, "Entrada Inválida", "Seleccione aseguradora y carpeta válida."
            )
            return

        self.log_text_edit.clear()
        self.log_text_edit.append(
            f"Preparando automatización para {self.combo_aseguradora.currentText()}..."
        )
        # self.ultima_carpeta_procesada = folder_path # No es crucial para habilitar reporte con JSON
        self._actualizar_estado_botones(proceso_corriendo=True)

        self.hilo_activo = QtCore.QThread(self)
        self.worker_activo = TrabajadorAutomatizacion(aseguradora_id, folder_path)
        self.worker_activo.moveToThread(self.hilo_activo)

        # Conectar señales
        self.worker_activo.progreso_update.connect(self._actualizar_log)
        self.worker_activo.finalizado.connect(self._manejar_finalizacion_worker)
        self.worker_activo.error_critico.connect(self._mostrar_error_critico)
        # Conexión para limpiar worker/hilo cuando el hilo termine
        self.hilo_activo.finished.connect(self.worker_activo.deleteLater)
        self.hilo_activo.finished.connect(self.hilo_activo.deleteLater)
        self.hilo_activo.finished.connect(
            self._limpiar_referencias_post_hilo
        )  # Usar slot diferente

        self.hilo_activo.started.connect(self.worker_activo.run_automation)
        self.hilo_activo.start()

    @QtCore.Slot()
    def _generar_reporte(self):
        """Inicia la generación del reporte."""
        if self.hilo_activo and self.hilo_activo.isRunning():
            QtWidgets.QMessageBox.warning(
                self, "Proceso Activo", "Ya hay un proceso en curso."
            )
            return
        folder_path = self.folder_line_edit.text()
        ruta_resultados_json = Path(folder_path) / "resultados_automatizacion.json"
        if not folder_path or folder_path == "..." or not os.path.isdir(folder_path):
            QtWidgets.QMessageBox.warning(
                self, "Selección Requerida", "Seleccione carpeta válida."
            )
            return
        if not ruta_resultados_json.is_file():
            QtWidgets.QMessageBox.warning(
                self,
                "Archivo Faltante",
                f"No se encontró '{ruta_resultados_json.name}'.\nEjecute automatización primero.",
            )
            return

        self.log_text_edit.clear()
        self.log_text_edit.append(f"Preparando reporte...")
        self._actualizar_estado_botones(proceso_corriendo=True)

        self.hilo_activo = QtCore.QThread(self)
        self.worker_activo = TrabajadorReporte(folder_path)
        self.worker_activo.moveToThread(self.hilo_activo)

        # Conectar señales
        self.worker_activo.progreso_update.connect(self._actualizar_log)
        self.worker_activo.finalizado.connect(self._manejar_finalizacion_worker)
        self.worker_activo.error_critico.connect(self._mostrar_error_critico)
        # Conexión para limpiar worker/hilo cuando el hilo termine
        self.hilo_activo.finished.connect(self.worker_activo.deleteLater)
        self.hilo_activo.finished.connect(self.hilo_activo.deleteLater)
        self.hilo_activo.finished.connect(
            self._limpiar_referencias_post_hilo
        )  # Usar slot diferente

        self.hilo_activo.started.connect(self.worker_activo.run_report_generation)
        self.hilo_activo.start()

    @QtCore.Slot(str)
    def _actualizar_log(self, mensaje):
        """Añade mensaje al log y hace scroll."""
        self.log_text_edit.append(mensaje)
        self.log_text_edit.verticalScrollBar().setValue(
            self.log_text_edit.verticalScrollBar().maximum()
        )

    # --- Slot unificado para manejar finalización ---
    @QtCore.Slot()
    def _manejar_finalizacion_worker(self, *args):
        """
        Slot que se ejecuta cuando CUALQUIER worker emite 'finalizado'.
        Actualiza la GUI y programa la limpieza del hilo/worker para más tarde.
        """
        print(
            f"DEBUG: Señal 'finalizado' recibida con args: {args} para worker tipo: {type(self.worker_activo).__name__ if self.worker_activo else 'None'}"
        )
        
        if not self.hilo_activo:
            print("ADVERTENCIA: 'finalizado' recibido pero el hilo ya no existe. Ignorando.")
            return

        carpeta_finalizada = self.folder_line_edit.text()  # Carpeta actual en la GUI
        worker_type = type(self.worker_activo) if self.worker_activo else None
        titulo_popup = "Proceso Finalizado"
        mensaje_popup = "Tarea terminada."
        mostrar_popup = False

        # Procesar resultados según el tipo de worker
        if (
            worker_type is TrabajadorAutomatizacion and len(args) == 5
        ):  # exitos, fallos, omit_rad, omit_dup, retry_fail
            exitos, fallos, omit_rad, omit_dup, retry_fail = args
            log_msg = f"\nAutomatización completada. É:{exitos}, F:{fallos}, OR:{omit_rad}, OD:{omit_dup}, FR:{retry_fail}"
            self._actualizar_log(log_msg)
            titulo_popup = "Automatización Finalizada"
            mensaje_popup = f"Completado en:\n{os.path.basename(carpeta_finalizada)}\n\nÉxitos: {exitos}\nFallos: {fallos}\nOmitidas(RAD): {omit_rad}\nOmitidas(Dup): {omit_dup}\nFallo Reintento: {retry_fail}"
            mostrar_popup = True
        elif worker_type is TrabajadorReporte and len(args) == 2:  # exito, mensaje
            exito, mensaje = args
            log_msg = f"\nGeneración reporte: {mensaje}"
            self._actualizar_log(log_msg)
            if exito:
                resp = QtWidgets.QMessageBox.information(
                    self,
                    "Reporte Generado",
                    f"Éxito.\n{mensaje}\n\n¿Abrir carpeta?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.Yes,
                )
                if (
                    resp == QtWidgets.QMessageBox.StandardButton.Yes
                    and carpeta_finalizada
                ):
                    self._abrir_carpeta(carpeta_finalizada)
            else:
                QtWidgets.QMessageBox.warning(
                    self, "Error en Reporte", f"Fallo:\n{mensaje}"
                )
            mostrar_popup = False  # Ya mostramos específico
        else:
            self._actualizar_log(
                f"\nWorker finalizado (tipo={worker_type}, args={args})."
            )
            mensaje_popup = "Tarea finalizada."
            mostrar_popup = True

        # --- ACTUALIZAR BOTONES INMEDIATAMENTE ---
        # La limpieza real del hilo/worker ocurrirá cuando se emita 'finished'
        self._actualizar_estado_botones(proceso_corriendo=False)

        # --- Mostrar Pop-up Info (si aplica) ---
        if mostrar_popup:
            QtWidgets.QMessageBox.information(self, titulo_popup, mensaje_popup)
        # NO limpiar referencias aquí, esperar a _limpiar_referencias_post_hilo

        self.hilo_activo.quit()
    @QtCore.Slot(str)
    def _mostrar_error_critico(self, mensaje_error):
        """Maneja errores críticos."""
        self.log_text_edit.append(f"\n!!! ERROR CRÍTICO !!!\n{mensaje_error}")
        QtWidgets.QMessageBox.critical(self, "Error Crítico", mensaje_error)
        # NO limpiar referencias aquí, esperar a _limpiar_referencias_post_hilo
        # Actualizar botones inmediatamente tras error
        if not self.hilo_activo:
            return

        self._actualizar_estado_botones(proceso_corriendo=False)
        
        self.hilo_activo.quit()                

    @QtCore.Slot()
    def _limpiar_referencias_post_hilo(self):
        """Limpia referencias DESPUÉS de que la señal 'finished' del hilo se emita."""
        print("DEBUG: Hilo finalizado. Limpiando referencias self.hilo/worker.")
        self.hilo_activo = None
        self.worker_activo = None
        # Asegurarse de que los botones estén habilitados
        self._actualizar_estado_botones(proceso_corriendo=False)

    def _actualizar_estado_botones(self, proceso_corriendo: bool):
        """Actualiza habilitación de controles."""
        habilitar_controles = not proceso_corriendo
        folder_path_str = self.folder_line_edit.text()
        es_carpeta_valida = os.path.isdir(folder_path_str) and folder_path_str != "..."
        self.start_button.setEnabled(habilitar_controles and es_carpeta_valida)
        reporte_habilitado = False
        if habilitar_controles and es_carpeta_valida:
            ruta_json = Path(folder_path_str) / "resultados_automatizacion.json"
            if ruta_json.is_file():
                reporte_habilitado = True
        self.report_button.setEnabled(reporte_habilitado)
        self.combo_aseguradora.setEnabled(habilitar_controles)
        self.browse_button.setEnabled(habilitar_controles)

    # --- Métodos para bandeja y cierre ---
    @QtCore.Slot(QtWidgets.QSystemTrayIcon.ActivationReason)
    def _icono_bandeja_activado(self, reason):
        """Maneja clics en el icono de la bandeja."""
        if (
            reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger
            or reason == QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick
        ):
            self._mostrar_ventana_desde_bandeja()

    @QtCore.Slot()
    def _mostrar_ventana_desde_bandeja(self):
        """Muestra y activa la ventana principal SIN ocultar el icono."""
        # No ocultar el icono aquí
        self.showNormal()
        self.raise_()
        self.activateWindow()

    @QtCore.Slot()
    def _salir_aplicacion(self):
        """Cierra la aplicación completamente."""
        print("Saliendo de la aplicación...")
        if self.hilo_activo and self.hilo_activo.isRunning():
            resp = QtWidgets.QMessageBox.warning(
                self,
                "Salir",
                "Proceso activo. ¿Salir?",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if resp == QtWidgets.QMessageBox.StandardButton.No:
                return
        if self.tray_icon:
            self.tray_icon.hide()
        QtWidgets.QApplication.instance().quit()

    def _abrir_carpeta(self, folder_path):
        """Abre la carpeta especificada."""
        if folder_path and os.path.isdir(folder_path):
            try:
                QtGui.QDesktopServices.openUrl(
                    QtCore.QUrl.fromLocalFile(os.path.abspath(folder_path))
                )
            except Exception as e:
                self._actualizar_log(f"Error abrir carpeta: {e}")
        else:
            self._actualizar_log(f"Ruta inválida: {folder_path}")

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Minimiza a la bandeja si está disponible, si no, cierra."""
        if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable() and self.tray_icon:
            # Minimizar a bandeja
            if self.hilo_activo and self.hilo_activo.isRunning():
                resp = QtWidgets.QMessageBox.question(
                    self,
                    "Proceso Activo",
                    "Proceso en curso. ¿Minimizar?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.Yes,
                )
                if resp == QtWidgets.QMessageBox.StandardButton.No:
                    event.ignore()
                    return

            print("Minimizando a la bandeja...")
            self.hide()
            self.tray_icon.show()  # Asegurarse que se muestre al minimizar
            icon_to_show = (
                self.app_icon
                if self.app_icon
                else QtWidgets.QSystemTrayIcon.Icon.Information
            )
            self.tray_icon.showMessage(
                "Minimizado",
                "Automatizador SOAT sigue ejecutándose.",
                icon_to_show,
                3000,
            )
            event.ignore()  # IGNORAR evento de cierre
        else:
            # Comportamiento de cierre normal
            print("Bandeja no disponible, cerrando ventana...")
            if self.hilo_activo and self.hilo_activo.isRunning():
                resp = QtWidgets.QMessageBox.question(
                    self,
                    "Proceso Activo",
                    "Proceso en curso. ¿Salir?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.No,
                )
                if resp == QtWidgets.QMessageBox.StandardButton.Yes:
                    event.accept()
                else:
                    event.ignore()
            else:
                event.accept()


# --- Código de ejecución va en main.py ---
