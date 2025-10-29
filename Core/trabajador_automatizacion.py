# Core/trabajador_automatizacion.py

import os
import time
import traceback
import importlib
from pathlib import Path
from PySide6 import QtCore
import json
import queue
from Automatizaciones.glosas import mundial_escolar
from playwright.sync_api import sync_playwright, Error as PlaywrightError
from Configuracion.constantes import MUNDIAL_ESCOLAR_URL

# Importaciones de configuración y otros trabajadores
from Configuracion.constantes import (
    AREA_GLOSAS_ID,
    AREA_FACTURACION_ID,
    ASEGURADORAS_CON_EMAIL_LISTENER,
    PREVISORA_ID,
    MUNDIAL_ESCOLAR_ID,
    MUNDIAL_ESCOLAR_SEDE1_USER,
    MUNDIAL_ESCOLAR_SEDE1_PASS,
    MUNDIAL_ESCOLAR_SEDE2_USER,
    MUNDIAL_ESCOLAR_SEDE2_PASS
)
from .trabajador_email import EmailListenerWorker
from .utilidades import consolidar_radicados_pdf, separar_carpetas_por_sede
from Automatizaciones.glosas import mundial_escolar

class TrabajadorAutomatizacion(QtCore.QObject):
    # --- Señales para comunicación con la GUI ---
    progreso_update = QtCore.Signal(str)
    finalizado = QtCore.Signal(int, int, int, int, int)
    error_critico = QtCore.Signal(str)

    def __init__(self, area_id, aseguradora_id, carpeta_contenedora, modo_headless):
        super().__init__()
        self.area_id = area_id
        self.aseguradora_id = aseguradora_id
        self.carpeta_contenedora_path = Path(carpeta_contenedora).resolve()
        self.headless_mode = modo_headless
        self.email_job_queue = queue.Queue()
        self.email_final_failures = []
        self.email_thread = None
        self.email_worker = None

        # Listas para la nueva reportería estructurada
        self.resultados_exitosos = []
        self.reporte_fallos = []
        self.reporte_omitidos = []

    @QtCore.Slot(list)
    def handle_email_failures(self, failed_jobs):
        """Slot que recibe la lista de fallos definitivos del hilo de email."""
        self.email_final_failures = failed_jobs

    def _iniciar_email_listener_si_es_necesario(self):
        """Inicia el hilo de escucha de email solo para las aseguradoras que lo requieren."""
        if self.aseguradora_id in ASEGURADORAS_CON_EMAIL_LISTENER:
            self.progreso_update.emit("[INFO] Esta aseguradora requiere el listener de email. Iniciando hilo...")
            self.email_thread = QtCore.QThread(self)
            self.email_worker = EmailListenerWorker(self.email_job_queue)
            self.email_worker.moveToThread(self.email_thread)
            self.email_worker.progreso_update.connect(self.progreso_update)
            self.email_worker.finished.connect(self.handle_email_failures)
            self.email_thread.started.connect(self.email_worker.run)
            self.email_thread.start()
        else:
            self.progreso_update.emit("[INFO] Esta aseguradora no requiere el listener de email.")

    def _formatear_tiempo(self, total_segundos: float) -> str:
        """Formatea segundos en un string legible (horas, minutos, segundos)."""
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
        """El método principal que orquesta todo el proceso de automatización."""
        self.progreso_update.emit(f"--- INICIANDO AUTOMATIZACIÓN ---")
        self.progreso_update.emit(f"Área: '{self.area_id}', Aseguradora: '{self.aseguradora_id}'")

        # Inicializar contadores y listas de reporte para esta ejecución
        exitos, fallos, omit_rad, omit_dup = 0, 0, 0, 0
        start_time = time.time()
        self.resultados_exitosos = []
        self.reporte_fallos = []
        self.reporte_omitidos = []

        if self.aseguradora_id == MUNDIAL_ESCOLAR_ID:
            self.run_mundial_escolar_automation()
            return

        self._iniciar_email_listener_si_es_necesario()
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless_mode, slow_mo=50)
                page = browser.new_context().new_page()

                # Carga dinámica del módulo de automatización específico
                module_path = f"Automatizaciones.{self.area_id}.{self.aseguradora_id}"
                try:
                    automation_module = importlib.import_module(module_path)
                    login_func = automation_module.login
                    navegar_inicio_func = automation_module.navegar_a_inicio
                    procesar_carpeta_func = automation_module.procesar_carpeta
                    ESTADO_EXITO = automation_module.ESTADO_EXITO
                    ESTADO_FALLO = automation_module.ESTADO_FALLO
                    ESTADO_OMITIDO_RADICADO = getattr(automation_module, 'ESTADO_OMITIDO_RADICADO', 'OMITIDO_RAD')
                    ESTADO_OMITIDO_DUPLICADA = getattr(automation_module, 'ESTADO_OMITIDO_DUPLICADA', 'OMITIDO_DUP')
                except (ImportError, AttributeError) as e:
                    raise Exception(f"No se pudo cargar la implementación para '{self.area_id}/{self.aseguradora_id}': {e}")

                login_ok, login_log = login_func(page); self.progreso_update.emit(login_log)
                if not login_ok: raise Exception("Login fallido.")

                nav_ok, nav_log = navegar_inicio_func(page); self.progreso_update.emit(nav_log)
                if not nav_ok: raise Exception("Navegación inicial fallida.")

                # --- Lógica de descubrimiento de trabajos ---
                jobs = []
                root_path = self.carpeta_contenedora_path
                self.progreso_update.emit(f"Analizando carpetas en: {root_path}")

                for item in root_path.iterdir():
                    if not item.is_dir():
                        continue

                    # Caso especial para la carpeta 'aceptadas'
                    if item.name.lower() == 'aceptadas':
                        self.progreso_update.emit("  -> Carpeta 'aceptadas' encontrada. Buscando subcarpetas...")
                        for sub_item in item.iterdir():
                            if sub_item.is_dir():
                                jobs.append((sub_item, 'aceptadas'))
                    else:
                        # Caso para las carpetas normales en la raíz
                        jobs.append((item, 'default'))
                
                # Ordenar los trabajos para asegurar que 'default' se procese antes que 'aceptadas'
                sort_order = {'default': 0, 'aceptadas': 1}
                jobs.sort(key=lambda x: (sort_order.get(x[1], 99), int(x[0].name) if x[0].name.isdigit() else float('inf')))

                subcarpetas_a_procesar = [job[0] for job in jobs]
                self.progreso_update.emit(f"Se procesarán {len(subcarpetas_a_procesar)} subcarpetas en total." if subcarpetas_a_procesar else "No hay subcarpetas para procesar.")
                # --- Fin de la lógica de descubrimiento ---

                for i, (subfolder_path, context) in enumerate(jobs):
                    self.progreso_update.emit(f"\n>>> Procesando Carpeta {i+1}/{len(jobs)}: '{subfolder_path.name}' (Contexto: {context})")
                    
                    # Llamada a la función con el nuevo argumento de contexto
                    estado, radicado, codigo_factura, log_carpeta = procesar_carpeta_func(page, subfolder_path, subfolder_path.name, context=context)
                    
                    self.progreso_update.emit(log_carpeta)

                    # Clasificación de resultados para reportes separados
                    if estado == ESTADO_EXITO:
                        exitos += 1
                        if self.email_thread and self.email_thread.isRunning():
                            self.email_job_queue.put((radicado, subfolder_path))
                        self.resultados_exitosos.append({"subcarpeta": subfolder_path.name, "factura": codigo_factura, "radicado": radicado})
                    elif estado == ESTADO_FALLO:
                        fallos += 1
                        self.reporte_fallos.append(log_carpeta)
                    elif estado == ESTADO_OMITIDO_RADICADO:
                        omit_rad += 1
                        motivo = log_carpeta.strip().split('\n')[-1]
                        self.reporte_omitidos.append(f"Carpeta: {subfolder_path.name:<15} -> {motivo}")
                    elif estado == ESTADO_OMITIDO_DUPLICADA:
                        omit_dup += 1
                        motivo = log_carpeta.strip().split('\n')[-1]
                        self.reporte_omitidos.append(f"Carpeta: {subfolder_path.name:<15} -> {motivo}")
                
                browser.close()

        except Exception as e:
            self.error_critico.emit(f"ERROR CRÍTICO DURANTE AUTOMATIZACIÓN:\n{e}\n{traceback.format_exc()}")
        
        finally:
            # Esperar a que el hilo de email termine si fue iniciado
            if self.email_thread and self.email_thread.isRunning():
                self.email_job_queue.put(None)
                self.email_thread.quit()
                if not self.email_thread.wait(600000):
                    self.progreso_update.emit("[ADVERTENCIA] El hilo de email tardó demasiado en terminar.")
                self.progreso_update.emit("Listener de email finalizado.")
            
            # --- Generación de Reportes Estructurados ---
            self.progreso_update.emit("\nGenerando archivos de reporte...")

            if self.resultados_exitosos:
                ruta_json = self.carpeta_contenedora_path / "resultados_automatizacion.json"
                with open(ruta_json, "w", encoding="utf-8") as f: json.dump(self.resultados_exitosos, f, indent=4)
                self.progreso_update.emit("[INFO] Reporte de éxitos (JSON) guardado.")

            if self.reporte_fallos:
                ruta_fallos = self.carpeta_contenedora_path / "reporte_FALLOS.txt"
                with open(ruta_fallos, "w", encoding="utf-8") as f:
                    f.write(f"--- REPORTE DE {len(self.reporte_fallos)} CARPETAS CON ERRORES ---\n")
                    f.write("\n" + ("=" * 70) + "\n\n")
                    f.write(("\n" + ("=" * 70) + "\n\n").join(self.reporte_fallos))
                self.progreso_update.emit(f"[INFO] Reporte de fallos guardado en: reporte_FALLOS.txt")

            if self.reporte_omitidos:
                ruta_omitidos = self.carpeta_contenedora_path / "reporte_OMITIDOS.txt"
                with open(ruta_omitidos, "w", encoding="utf-8") as f:
                    f.write(f"--- REPORTE DE {omit_rad + omit_dup} CARPETAS OMITIDAS ---\n\n")
                    f.write("\n".join(self.reporte_omitidos))
                self.progreso_update.emit(f"[INFO] Reporte de omisiones guardado en: reporte_OMITIDOS.txt")
            
            # Consolidación condicional de PDFs
            if self.area_id == AREA_FACTURACION_ID and self.aseguradora_id == PREVISORA_ID and self.resultados_exitosos:
                _, log_consolidacion = consolidar_radicados_pdf(self.carpeta_contenedora_path)
                self.progreso_update.emit(log_consolidacion)
            
            # Compilación del resumen final para la GUI
            total_time = time.time() - start_time
            tiempo_formateado = self._formatear_tiempo(total_time)
            email_fallos_count = len(self.email_final_failures)
            
            linea_sep = '\n' + ('=' * 45)
            summary_lines = [
                linea_sep,
                "--- FIN DEL PROCESO DE AUTOMATIZACIÓN ---",
                "\nResultados del Proceso Web:",
                f"  - Éxitos: \t\t{exitos}",
                f"  - Fallos: \t\t{fallos}",
                f"  - Omitidas (ya radicadas): {omit_rad}",
                f"  - Omitidas (factura duplicada): {omit_dup}",
            ]

            if self.aseguradora_id in ASEGURADORAS_CON_EMAIL_LISTENER:
                summary_lines.append("\nResultados del Proceso Email:")
                summary_lines.append(f"  - Correos no encontrados: {email_fallos_count}")
            
            summary_lines.extend([
                f"\n\nTiempo Total de Ejecución: {tiempo_formateado}",
                linea_sep
            ])
            summary_msg = "\n".join(summary_lines)
            self.progreso_update.emit(summary_msg)
            
            # Envío de la señal final a la GUI para reactivar botones
            self.finalizado.emit(exitos, fallos, omit_rad, omit_dup, email_fallos_count)

    def run_mundial_escolar_automation(self):
        self.progreso_update.emit("--- INICIANDO MODO DE PRUEBA DE LÓGICA (SIN NAVEGADOR) ---")
        start_time = time.time()
        exitos, fallos, omitidos = 0, 0, 0

        try:
            # Esta parte no cambia: clasificación, ordenamiento y preparación de datos
            sede_1, sede_2, no_reconocidas = separar_carpetas_por_sede(self.carpeta_contenedora_path)
            omitidos = len(no_reconocidas)

            try:
                sede_1.sort(key=lambda glosa: int(glosa['factura']))
                sede_2.sort(key=lambda glosa: int(glosa['factura']))
                self.progreso_update.emit("[INFO] Listas de glosas ordenadas por número de factura.")
            except (ValueError, KeyError) as e:
                self.progreso_update.emit(f"[ADVERTENCIA] No se pudo ordenar las listas de glosas: {e}")

            for glosa_list in [sede_1, sede_2]:
                for glosa in glosa_list:
                    glosa['factura_completa'] = f"{glosa['prefijo'].strip()}{glosa['factura'].strip()}"

            self.progreso_update.emit("\n--- Clasificación de Carpetas (ordenadas) ---")
            self.progreso_update.emit(f"Sede 1 ({len(sede_1)} carpetas): " + ", ".join([os.path.basename(g['ruta']) for g in sede_1]))
            self.progreso_update.emit(f"Sede 2 ({len(sede_2)} carpetas): " + ", ".join([os.path.basename(g['ruta']) for g in sede_2]))
            # ... resto del log de clasificación ...

            # --- MODO DE PRUEBA: SOLO LLAMADAS A LA API Y LÓGICA ---
            self.progreso_update.emit("\n--- EJECUTANDO DIAGNÓSTICO DE DATOS ---")
            
            # Combinamos ambas sedes en una sola lista para la prueba
            todas_las_glosas = sede_1 + sede_2

            if not todas_las_glosas:
                self.progreso_update.emit("No hay glosas para diagnosticar.")
            
            for glosa in todas_las_glosas:
                self.progreso_update.emit(f"\nProcesando glosa de carpeta: {os.path.basename(glosa['ruta'])}")
                
                # Llamada a la nueva función de diagnóstico
                es_radicable, log_diagnostico, lote_para_procesar = mundial_escolar.diagnosticar_factura_desde_gema(glosa)
                
                # Imprimimos el resultado del diagnóstico
                self.progreso_update.emit(log_diagnostico)
                
                if es_radicable:
                    self.progreso_update.emit("  -> Veredicto: PROCEDER A RADICACIÓN (cuando se active el navegador).")
                    exitos += 1
                else:
                    self.progreso_update.emit("  -> Veredicto: NO RADICAR / OMITIR.")
                    fallos += 1 # Contamos los "no radicables" como fallos en esta prueba

        except Exception as e:
            self.error_critico.emit(f"!!! ERROR CRÍTICO !!!\nERROR CRÍTICO DURANTE MODO DE PRUEBA:\n{e}\n{traceback.format_exc()}")
        
        finally:
            total_time = time.time() - start_time
            tiempo_formateado = self._formatear_tiempo(total_time)
            
            summary_msg = (
                f"\n--- FIN DEL MODO DE PRUEBA ---\n"
                f"Facturas Radicables: {exitos}\n"
                f"Facturas No Radicables/Error: {fallos}\n"
                f"Omitidas (nombre de carpeta): {omitidos}\n"
                f"Tiempo Total: {tiempo_formateado}"
            )
            self.progreso_update.emit(summary_msg)
            self.finalizado.emit(exitos, fallos, omitidos, 0, 0)
