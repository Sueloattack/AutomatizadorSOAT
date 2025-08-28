# AutomatizadorSOAT/Core/trabajador_automatizacion.py (Versión final dinámica)

import os
import time
import traceback
import importlib  # La librería clave para la carga dinámica
from pathlib import Path
from PySide6 import QtCore
import json

from playwright.sync_api import sync_playwright, Error as PlaywrightError


class TrabajadorAutomatizacion(QtCore.QObject):
    progreso_update = QtCore.Signal(str)
    finalizado = QtCore.Signal(int, int, int, int, int)
    error_critico = QtCore.Signal(str)
    
    def __init__(self, area_id, aseguradora_id, carpeta_contenedora, modo_headless):
        super().__init__()
        self.area_id = area_id
        self.aseguradora_id = aseguradora_id
        self.carpeta_contenedora_path = Path(carpeta_contenedora).resolve()
        self.modo_headless = modo_headless
        self.resultados_exitosos = []

    @QtCore.Slot()
    def run_automation(self):
        # El log inicial ahora está aquí, usando los datos del __init__
        self.progreso_update.emit(f"--- INICIANDO AUTOMATIZACIÓN DINÁMICA ---")
        self.progreso_update.emit(f"Área: '{self.area_id}', Aseguradora: '{self.aseguradora_id}'")
        self.progreso_update.emit(f"Carpeta base: {self.carpeta_contenedora_path}")

        exitos, fallos, omit_rad, omit_dup, retry_fail = 0, 0, 0, 0, 0
        start_time = time.time()
        self.resultados_exitosos = []

        try:
            with sync_playwright() as p:
                self.progreso_update.emit(f"Iniciando navegador (Chromium)... Modo Headless: {self.modo_headless}")
                browser = p.chromium.launch(headless=self.modo_headless, slow_mo=50)
                context = browser.new_context()
                page = context.new_page()
                self.progreso_update.emit("Navegador iniciado correctamente.")

                # ================================================================= #
                # ===== INICIO DEL BLOQUE DE SELECCIÓN DE MÓDULO DINÁMICO ========= #
                # ================================================================= #
                
                self.progreso_update.emit(f"Buscando implementación de automatización...")
                try:
                    # 1. Construimos la ruta al módulo como un string.
                    #    Ej: "Automatizaciones.glosas.previsora"
                    #    Esto coincide con tu nueva estructura de carpetas y el nombre del archivo.
                    module_path = f"Automatizaciones.{self.area_id}.{self.aseguradora_id}"
                    
                    # 2. Usamos importlib para importar el módulo usando la ruta que construimos.
                    #    Esto es el equivalente dinámico de `from Automatizaciones.glosas import previsora`
                    automation_module = importlib.import_module(module_path)
                    self.progreso_update.emit(f"Módulo '{module_path}' cargado con éxito.")
                    
                    # 3. Asumimos que CADA módulo de automatización define un estándar de funciones.
                    #    (Ver la nota importante más abajo sobre estandarizar los nombres)
                    login_func = automation_module.login
                    navegar_inicio_func = automation_module.navegar_a_inicio
                    funcion_procesar_carpeta = automation_module.procesar_carpeta
                    
                    # 4. También obtenemos los estados desde el módulo cargado
                    ESTADO_EXITO = automation_module.ESTADO_EXITO
                    ESTADO_FALLO = automation_module.ESTADO_FALLO
                    ESTADO_OMITIDO_RADICADO = automation_module.ESTADO_OMITIDO_RADICADO
                    ESTADO_OMITIDO_DUPLICADA = automation_module.ESTADO_OMITIDO_DUPLICADA

                except (ImportError, AttributeError) as e:
                    # Si no encuentra el archivo o la función, falla de forma controlada.
                    error_msg = f"No se pudo encontrar la implementación para '{self.area_id}/{self.aseguradora_id}'.\nVerifique que el archivo 'Automatizaciones/{self.area_id}/{self.aseguradora_id}.py' exista y tenga las funciones correctas.\nError: {e}"
                    self.error_critico.emit(error_msg)
                    browser.close()
                    return

                # =============================================================== #
                # ===== FIN DEL BLOQUE DE SELECCIÓN DE MÓDULO DINÁMICO ========== #
                # =============================================================== #

                # Desde aquí, el resto del código no necesita saber de qué aseguradora se trata.
                # Simplemente usa las funciones genéricas que cargamos.
                
                self.progreso_update.emit("Realizando login inicial...")
                login_ok, login_log = login_func(page)
                self.progreso_update.emit(login_log)
                if not login_ok:
                    self.error_critico.emit("Fallo en login inicial. El proceso se detendrá.")
                    browser.close()
                    return

                self.progreso_update.emit("Navegando a página inicial de formularios...")
                nav_ok, nav_log = navegar_inicio_func(page)
                self.progreso_update.emit(nav_log)
                if not nav_ok:
                    self.error_critico.emit("Fallo crítico al navegar a la página de inicio.")
                    browser.close()
                    return

                # El resto de la función (ordenar carpetas, bucle for, etc.) sigue
                # exactamente igual a como la tenías, ya que es lógica genérica.
                
                subcarpetas = sorted(
                    [d for d in self.carpeta_contenedora_path.iterdir() if d.is_dir()],
                    key=lambda p: int(p.name) if p.name.isdigit() else float('inf')
                )

                if not subcarpetas:
                    self.progreso_update.emit("No se encontraron subcarpetas para procesar.")
                    browser.close(); self.finalizado.emit(0,0,0,0,0); return
                
                self.progreso_update.emit(f"Se procesarán {len(subcarpetas)} subcarpetas."); self.progreso_update.emit("=" * 40)

                for i, subfolder_path in enumerate(subcarpetas):
                    subfolder_name = subfolder_path.name
                    self.progreso_update.emit(f"\n>>> Procesando Carpeta {i+1}/{len(subcarpetas)}: '{subfolder_name}'")

                    estado, radicado, codigo_factura_devuelto, log_carpeta = funcion_procesar_carpeta(page, subfolder_path, subfolder_name)
                    self.progreso_update.emit(log_carpeta)

                    if estado == ESTADO_EXITO:
                        exitos += 1

                        resultado = {
                            "subcarpeta": subfolder_name,
                            "factura": codigo_factura_devuelto or "N/A",
                            "radicado": radicado or "No Extraído",
                            "rad_pdf_path": str(subfolder_path / "RAD.pdf"),
                        }

                        self.resultados_exitosos.append(resultado)
                    elif estado == ESTADO_FALLO: fallos += 1
                    elif estado == ESTADO_OMITIDO_RADICADO: omit_rad += 1
                    elif estado == ESTADO_OMITIDO_DUPLICADA: omit_dup += 1

                    self.progreso_update.emit("-" * 40)

                self.progreso_update.emit("\nCerrando navegador...")
                browser.close()

        except PlaywrightError as err:
            error_msg = f"ERROR CRÍTICO DE PLAYWRIGHT: {err}"
            self.progreso_update.emit(error_msg); traceback.print_exc(); self.error_critico.emit(error_msg)
        except Exception as e:
            error_msg = f"!!! ERROR CRÍTICO INESPERADO !!!\n{traceback.format_exc()}"
            self.progreso_update.emit(error_msg); self.error_critico.emit("Ocurrió un error crítico inesperado.")
        finally:
            if self.resultados_exitosos:
                ruta_json = self.carpeta_contenedora_path / "resultados_automatizacion.json"
                self.progreso_update.emit(f"\nGuardando {len(self.resultados_exitosos)} resultados en {ruta_json.name}...")
                with open(ruta_json, "w", encoding="utf-8") as f:
                    json.dump(self.resultados_exitosos, f, indent=4)
                self.progreso_update.emit("Resumen guardado.")
            
            end_time = time.time(); total_time = end_time - start_time
            summary_msg = f"""
{'='*40}
--- FIN AUTOMATIZACIÓN ---
Resumen del Proceso:
- Éxitos: {exitos}
- Fallos: {fallos}
- Omitidas (Ya tenían RAD): {omit_rad}
- Omitidas (Factura duplicada): {omit_dup}
- Fallos en Reintento: {retry_fail}

Tiempo Total: {total_time:.2f} segundos
{'='*40}"""
            self.progreso_update.emit(summary_msg)
            self.finalizado.emit(exitos, fallos, omit_rad, omit_dup, retry_fail)