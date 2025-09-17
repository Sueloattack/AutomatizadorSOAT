# AutomatizadorSOAT/Core/trabajador_automatizacion.py (Versión final con Omitidas Duplicadas corregido)

import time
import traceback
import importlib
from pathlib import Path
from PySide6 import QtCore
import json
import queue

from playwright.sync_api import sync_playwright, Error as PlaywrightError

from Configuracion.constantes import (
    AREA_GLOSAS_ID,
    AREA_FACTURACION_ID,
    ASEGURADORAS_CON_EMAIL_LISTENER,
    PREVISORA_ID
)
from .utilidades import consolidar_radicados_pdf
from .trabajador_email import EmailListenerWorker


class TrabajadorAutomatizacion(QtCore.QObject):
    progreso_update = QtCore.Signal(str)
    finalizado = QtCore.Signal(int, int, int, int, int)
    error_critico = QtCore.Signal(str)

    def __init__(self, area_id, aseguradora_id, carpeta_contenedora, modo_headless):
        super().__init__()
        self.area_id = area_id
        self.aseguradora_id = aseguradora_id
        self.carpeta_contenedora_path = Path(carpeta_contenedora).resolve()
        self.headless_mode = modo_headless
        self.resultados_exitosos = []
        self.email_job_queue = queue.Queue()
        self.email_final_failures = []
        self.email_thread = None

    @QtCore.Slot(list)
    def handle_email_failures(self, failed_jobs):
        self.email_final_failures = failed_jobs

    def _iniciar_email_listener_si_es_necesario(self):
        if self.area_id == AREA_GLOSAS_ID and self.aseguradora_id in ASEGURADORAS_CON_EMAIL_LISTENER:
            self.progreso_update.emit("[INFO] Iniciando listener de email...")
            self.email_thread = QtCore.QThread(self)
            email_worker = EmailListenerWorker(self.email_job_queue)
            email_worker.moveToThread(self.email_thread)
            email_worker.progreso_update.connect(self.progreso_update)
            email_worker.finished.connect(self.handle_email_failures)
            self.email_thread.started.connect(email_worker.run)
            self.email_thread.start()
        else:
            self.progreso_update.emit("[INFO] No se requiere listener de email para esta tarea.")

    def _formatear_tiempo(self, total_segundos: float) -> str:
        if total_segundos < 0: return "0 segundos"
        segundos_enteros = int(total_segundos)
        horas = segundos_enteros // 3600; segundos_enteros %= 3600
        minutos = segundos_enteros // 60; segundos = segundos_enteros % 60
        partes = []
        if horas > 0: partes.append(f"{horas} hora{'s' if horas != 1 else ''}")
        if minutos > 0: partes.append(f"{minutos} minuto{'s' if minutos != 1 else ''}")
        if segundos > 0 or not partes: partes.append(f"{segundos} segundo{'s' if segundos != 1 else ''}")
        return ", ".join(partes)

    @QtCore.Slot()
    def run_automation(self):
        self.progreso_update.emit(f"--- INICIANDO AUTOMATIZACIÓN ---")
        self.progreso_update.emit(f"Área: '{self.area_id}', Aseguradora: '{self.aseguradora_id}'")
        
        # <<< CORRECCIÓN: Volvemos a añadir omit_dup a los contadores >>>
        exitos, fallos, omit_rad, omit_dup = 0, 0, 0, 0
        self.resultados_exitosos = []
        start_time = time.time()

        self._iniciar_email_listener_si_es_necesario()
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless_mode, slow_mo=50)
                page = browser.new_context().new_page()

                module_path = f"Automatizaciones.{self.area_id}.{self.aseguradora_id}"
                try:
                    automation_module = importlib.import_module(module_path)
                    login_func, navegar_inicio_func, procesar_carpeta_func = (
                        automation_module.login, automation_module.navegar_a_inicio, automation_module.procesar_carpeta
                    )
                    ESTADO_EXITO = automation_module.ESTADO_EXITO
                    ESTADO_FALLO = automation_module.ESTADO_FALLO
                    ESTADO_OMITIDO_RADICADO = getattr(automation_module, 'ESTADO_OMITIDO_RADICADO', 'OMITIDO_RAD')
                    # <<< CORRECCIÓN: Leemos el estado OMITIDO_DUPLICADA del módulo cargado >>>
                    ESTADO_OMITIDO_DUPLICADA = getattr(automation_module, 'ESTADO_OMITIDO_DUPLICADA', 'OMITIDO_DUP')
                except (ImportError, AttributeError) as e:
                    raise Exception(f"No se pudo cargar la implementación: {e}")

                login_ok, login_log = login_func(page); self.progreso_update.emit(login_log)
                if not login_ok: raise Exception("Login fallido.")

                nav_ok, nav_log = navegar_inicio_func(page); self.progreso_update.emit(nav_log)
                if not nav_ok: raise Exception("Navegación inicial fallida.")

                subcarpetas = sorted([d for d in self.carpeta_contenedora_path.iterdir() if d.is_dir()], key=lambda p: int(p.name) if p.name.isdigit() else float('inf'))
                self.progreso_update.emit(f"Se procesarán {len(subcarpetas)} subcarpetas." if subcarpetas else "No hay subcarpetas para procesar.")

                for i, subfolder_path in enumerate(subcarpetas):
                    self.progreso_update.emit(f"\n>>> Procesando Carpeta {i+1}/{len(subcarpetas)}: '{subfolder_path.name}'")
                    estado, radicado, codigo_factura, log_carpeta = procesar_carpeta_func(page, subfolder_path, subfolder_path.name)
                    self.progreso_update.emit(log_carpeta)

                    # <<< CORRECCIÓN: Volvemos a contar las omitidas duplicadas >>>
                    if estado == ESTADO_EXITO and radicado:
                        exitos += 1
                        if self.email_thread and self.email_thread.isRunning():
                            self.email_job_queue.put((radicado, subfolder_path))
                            self.progreso_update.emit(f"[TRABAJADOR] Radicado {radicado} en cola para email.")
                        self.resultados_exitosos.append({"subcarpeta": subfolder_path.name, "factura": codigo_factura, "radicado": radicado})
                    elif estado == ESTADO_FALLO:
                        fallos += 1
                    elif estado == ESTADO_OMITIDO_RADICADO:
                        omit_rad += 1
                    elif estado == ESTADO_OMITIDO_DUPLICADA:
                        omit_dup += 1 # <- Línea reintroducida
                
                browser.close()

        except Exception as e:
            self.error_critico.emit(f"ERROR CRÍTICO DURANTE AUTOMATIZACIÓN:\n{e}\n{traceback.format_exc()}")
        
        finally:
            if self.email_thread and self.email_thread.isRunning():
                self.email_job_queue.put(None)
                self.email_thread.quit()
                if not self.email_thread.wait(600000):
                    self.progreso_update.emit("[ADVERTENCIA] El hilo de email tardó demasiado en terminar.")

            if self.resultados_exitosos:
                ruta_json = self.carpeta_contenedora_path / "resultados_automatizacion.json"
                with open(ruta_json, "w", encoding="utf-8") as f: json.dump(self.resultados_exitosos, f, indent=4)
                self.progreso_update.emit("Resumen de radicados web exitosos guardado.")
            
            if self.area_id == AREA_FACTURACION_ID and self.aseguradora_id == PREVISORA_ID and self.resultados_exitosos:
                _, log_consolidacion = consolidar_radicados_pdf(self.carpeta_contenedora_path)
                self.progreso_update.emit(log_consolidacion)
            
            total_time = time.time() - start_time
            tiempo_formateado = self._formatear_tiempo(total_time)
            email_fallos_count = len(self.email_final_failures)
            
            # <<< CORRECCIÓN: Mensaje de resumen ahora incluye las duplicadas >>>
            linea_sep = '\n' + ('=' * 45)
            summary_msg = f"{linea_sep}\n--- FIN DEL PROCESO DE AUTOMATIZACIÓN ---\n\n"
            summary_msg += "Resultados del Proceso Web:\n"
            summary_msg += f"  - Éxitos: \t\t{exitos}\n"
            summary_msg += f"  - Fallos: \t\t{fallos}\n"
            summary_msg += f"  - Omitidas (ya radicadas): {omit_rad}\n"
            summary_msg += f"  - Omitidas (factura duplicada): {omit_dup}\n\n"

            if self.area_id == AREA_GLOSAS_ID and self.aseguradora_id in ASEGURADORAS_CON_EMAIL_LISTENER:
                summary_msg += f"Resultados del Proceso Email:\n"
                summary_msg += f"  - Correos no encontrados: {email_fallos_count}\n\n"
            
            summary_msg += f"Tiempo Total de Ejecución: {tiempo_formateado}\n{linea_sep}"
            
            self.progreso_update.emit(summary_msg)
            
            # <<< CORRECCIÓN: Enviamos todos los contadores correctamente en la señal >>>
            self.finalizado.emit(exitos, fallos, omit_rad, omit_dup, email_fallos_count)