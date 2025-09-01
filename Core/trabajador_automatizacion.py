# Core/trabajador_automatizacion.py (Versión Final con Hilo de Email)

import os
import time
import traceback
import importlib
from pathlib import Path
from PySide6 import QtCore
import json
import queue # Importamos la librería de colas

from playwright.sync_api import sync_playwright, Error as PlaywrightError

from Configuracion.constantes import ASEGURADORAS_CON_EMAIL_LISTENER

# Importamos nuestro nuevo trabajador de email
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

    @QtCore.Slot(list)
    def handle_email_failures(self, failed_jobs):
        self.email_final_failures = failed_jobs
        
    @QtCore.Slot()
    def run_automation(self):
        # --- Fase 1: Inicialización y Preparación ---
        self.progreso_update.emit(f"--- INICIANDO AUTOMATIZACIÓN DINÁMICA ---")
        self.progreso_update.emit(f"Área: '{self.area_id}', Aseguradora: '{self.aseguradora_id}'")
        
        exitos, fallos, omit_rad, omit_dup = 0, 0, 0, 0
        start_time = time.time()
        self.resultados_exitosos = []
        
        # --- Fase 2: Lanzamiento Condicional del Hilo de Email ---
        self.email_thread = None
        if self.aseguradora_id in ASEGURADORAS_CON_EMAIL_LISTENER:
            self.progreso_update.emit("[INFO] Esta aseguradora requiere el listener de email. Iniciando hilo...")
            self.email_thread = QtCore.QThread()
            self.email_worker = EmailListenerWorker(self.email_job_queue)
            self.email_worker.moveToThread(self.email_thread)
            self.email_worker.progreso_update.connect(self.progreso_update)
            self.email_worker.finished.connect(self.handle_email_failures)
            self.email_thread.started.connect(self.email_worker.run)
            self.email_thread.start()
        else:
            self.progreso_update.emit("[INFO] Esta aseguradora no requiere el listener de email.")
            
        try:
            # --- Fase 3: Proceso de Radicación Web con Playwright ---
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless_mode, slow_mo=50)
                context = browser.new_context()
                page = context.new_page()
                self.progreso_update.emit("Navegador iniciado correctamente.")

                # Carga dinámica del módulo especialista
                try:
                    module_path = f"Automatizaciones.{self.area_id}.{self.aseguradora_id}"
                    automation_module = importlib.import_module(module_path)
                    login_func = automation_module.login
                    navegar_inicio_func = automation_module.navegar_a_inicio
                    funcion_procesar_carpeta = automation_module.procesar_carpeta
                    ESTADO_EXITO = automation_module.ESTADO_EXITO
                    ESTADO_FALLO = automation_module.ESTADO_FALLO
                    ESTADO_OMITIDO_RADICADO = getattr(automation_module, 'ESTADO_OMITIDO_RADICADO', 'OMITIDO_RADICADO')
                    ESTADO_OMITIDO_DUPLICADA = getattr(automation_module, 'ESTADO_OMITIDO_DUPLICADA', 'OMITIDO_DUPLICADA')
                except (ImportError, AttributeError) as e:
                    raise Exception(f"No se pudo encontrar la implementación para '{self.area_id}/{self.aseguradora_id}'.\nError: {e}")

                # Login y Navegación inicial
                login_ok, login_log = login_func(page); self.progreso_update.emit(login_log)
                if not login_ok: raise Exception("Login fallido")

                nav_ok, nav_log = navegar_inicio_func(page); self.progreso_update.emit(nav_log)
                if not nav_ok: raise Exception("Navegación inicial fallida")

                # Bucle de procesamiento de carpetas
                subcarpetas = sorted([d for d in self.carpeta_contenedora_path.iterdir() if d.is_dir()], key=lambda p: int(p.name) if p.name.isdigit() else float('inf'))
                self.progreso_update.emit(f"Se procesarán {len(subcarpetas)} subcarpetas." if subcarpetas else "No se encontraron subcarpetas para procesar.")

                for i, subfolder_path in enumerate(subcarpetas):
                    self.progreso_update.emit(f"\n>>> Procesando WEB Carpeta {i+1}/{len(subcarpetas)}: '{subfolder_path.name}'")
                    estado, radicado, codigo_factura, log_carpeta = funcion_procesar_carpeta(page, subfolder_path, subfolder_path.name)
                    self.progreso_update.emit(log_carpeta)

                    if estado == ESTADO_EXITO and radicado:
                        exitos += 1
                        if self.email_thread: # Solo poner en cola si el hilo de email existe
                            self.email_job_queue.put((radicado, subfolder_path))
                            self.progreso_update.emit(f"[AUTOMATIZADOR] Trabajo para radicado {radicado} enviado a la cola de email.")
                        resultado = {"subcarpeta": subfolder_path.name, "factura": codigo_factura, "radicado": radicado}
                        self.resultados_exitosos.append(resultado)
                    elif estado == ESTADO_FALLO: fallos += 1
                    elif estado == ESTADO_OMITIDO_RADICADO: omit_rad += 1
                    elif estado == ESTADO_OMITIDO_DUPLICADA: omit_dup += 1

                self.progreso_update.emit("\nCerrando navegador...")
                browser.close() # Cierre seguro dentro del 'with'

        except Exception as e:
            self.error_critico.emit(f"ERROR CRÍTICO: {e}\n{traceback.format_exc()}")
        finally:
            # --- Fase 4: Cierre Limpio y Reporte ---
            if self.email_thread:
                self.progreso_update.emit("\nAutomatización web finalizada. Dando la orden final al listener de email...")
                self.email_job_queue.put(None)
                self.email_thread.quit()
                exito_espera = self.email_thread.wait(600000)
                if not exito_espera: self.progreso_update.emit("[ADVERTENCIA] El hilo de email tardó demasiado en terminar.")
                self.progreso_update.emit("Listener de email finalizado.")

            if self.resultados_exitosos:
                ruta_json = self.carpeta_contenedora_path / "resultados_automatizacion.json"
                with open(ruta_json, "w", encoding="utf-8") as f: json.dump(self.resultados_exitosos, f, indent=4)
                self.progreso_update.emit("Resumen de éxitos guardado.")
            
            end_time = time.time(); total_time = end_time - start_time
            email_failures_count = len(self.email_final_failures)
            
            linea_sep = '\n' + ('=' * 40); summary_lines = [
                linea_sep, "--- FIN AUTOMATIZACIÓN ---", "Resumen Web:",
                f"  Éxitos({exitos})", f"  Fallos({fallos})",
                f"  Omitidas por Exclusión/RAD({omit_rad})", f"  Omitidas por Duplicado({omit_dup})", ""
            ]
            if self.aseguradora_id in ASEGURADORAS_CON_EMAIL_LISTENER:
                summary_lines.append(f"Resumen Email: {email_failures_count} correo(s) NO encontrados.")
                summary_lines.append("")
            summary_lines.extend([f"Tiempo Total: {total_time:.2f} segundos", linea_sep])
            summary_msg = "\n".join(summary_lines)
            self.progreso_update.emit(summary_msg)

            self.finalizado.emit(exitos, fallos, omit_rad + omit_dup, 0, email_failures_count)