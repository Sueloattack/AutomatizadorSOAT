# AutomatizadorSOAT/nucleo/trabajador_automatizacion.py
import os
import time
import traceback
from pathlib import Path
from PySide6 import QtCore
import json  # Para guardar resultados

try:
    # No necesitamos importar todo Selenium aquí, solo WebDriverException si la capturamos directamente
    from selenium.common.exceptions import WebDriverException
except ImportError:
    print("ERROR CRÍTICO: Faltan dependencias de Selenium.")
    raise ImportError("Faltan dependencias de Selenium. Ejecuta: pip install selenium")
# Importar utilidades y constantes
# ¡¡ASEGÚRATE DE QUE LOS NOMBRES DE CARPETA SEAN CORRECTOS!!
# Cambia 'Core' a 'nucleo' y 'Configuracion' a 'configuracion' si es necesario
try:
    from Core.utilidades import configurar_driver, cerrar_driver
except ImportError as e:
    print(f"ERROR CRITICO: Importar utilidades ({e}). Verifica ruta 'nucleo'.")
    raise

try:
    from Configuracion.constantes import PREVISORA_ID, MUNDIAL_ID, AXA_ID
except ImportError as e:
    print(f"ERROR CRITICO: Importar constantes ({e}). Verifica ruta 'configuracion'.")
    raise

# Importar estados de retorno del módulo de automatización específico
# Asegúrate que la ruta sea correcta si la carpeta es 'automatizaciones'
try:
    from Automatizaciones.previsora import (
        ESTADO_EXITO,
        ESTADO_FALLO,
        ESTADO_OMITIDO_RADICADO,
        ESTADO_OMITIDO_DUPLICADA,
        # Ya no necesitamos importar ESTADO_SESION_EXPIRADA ni reintentar_login...
    )
except ImportError as e:
    print(f"ERROR CRITICO: Importar estados desde 'automatizaciones.previsora' ({e}).")
    # Definir aquí como fallback si falla la importación, aunque es mejor arreglar el import
    ESTADO_EXITO = "EXITO"
    ESTADO_FALLO = "FALLO"
    ESTADO_OMITIDO_RADICADO = "OMITIDO_RADICADO"
    ESTADO_OMITIDO_DUPLICADA = "OMITIDO_DUPLICADA"
    # raise # Opcional: detener si no se pueden importar estados


class TrabajadorAutomatizacion(QtCore.QObject):
    """
    Clase QObject que ejecuta la lógica de automatización en un hilo separado.
    Ordena las subcarpetas numéricamente antes de procesar.
    Guarda resultados exitosos en un JSON.
    Navega a la página de inicio UNA VEZ después del login.
    Emite señales para comunicar el progreso y resultados a la GUI.
    """

    # --- Señales ---
    progreso_update = QtCore.Signal(str)
    # Ajustado para enviar: exitos, fallos, omit_rad, omit_dup
    finalizado = QtCore.Signal(int, int, int, int)
    error_critico = QtCore.Signal(str)
    # Ya no necesitamos conexion_perdida si usamos error_critico para todo

    def __init__(self, aseguradora_id, carpeta_contenedora):
        super().__init__()
        self.aseguradora_id = aseguradora_id
        self.carpeta_contenedora_path = Path(carpeta_contenedora).resolve()
        self._detener = False
        self.resultados_exitosos = (
            []
        )  # Guardará dicts {subcarpeta, factura, radicado, rad_pdf_path}

    @QtCore.Slot()
    def run_automation(self):
        """Método principal que ejecuta la automatización."""
        self.progreso_update.emit(
            f"--- INICIANDO AUTOMATIZACIÓN ({self.aseguradora_id.upper()}) ---"
        )
        self.progreso_update.emit(f"Carpeta base: {self.carpeta_contenedora_path}")

        driver = None
        wait = None
        carpetas_exitosas = 0
        carpetas_fallidas = 0
        carpetas_omitidas_rad = 0
        carpetas_omitidas_dup = 0
        start_time = time.time()
        self.resultados_exitosos = []  # Reiniciar resultados

        try:
            # 1. Configurar WebDriver
            self.progreso_update.emit("Configurando WebDriver...")
            driver, wait, driver_log = configurar_driver(
                headless=True
            )  # O False para debug
            self.progreso_update.emit(driver_log)
            if driver is None or wait is None:
                self.error_critico.emit(driver_log)
                return

            # 2. Seleccionar Módulo y Funciones
            funcion_procesar_carpeta = None
            login_func = None
            navegar_inicio_func = None
            modulo_nombre = ""
            if self.aseguradora_id == PREVISORA_ID:
                modulo_nombre = "Previsora"
                try:
                    # Asegúrate que la ruta sea correcta (automatizaciones)
                    from Automatizaciones import previsora

                    funcion_procesar_carpeta = previsora.procesar_carpeta_previsora
                    login_func = previsora.login_previsora
                    navegar_inicio_func = previsora.navegar_a_inicio_previsora
                except ImportError as ie:
                    raise ImportError(
                        f"No se pudo importar módulo {modulo_nombre}: {ie}"
                    )
            # --- elif para otras aseguradoras ---
            else:
                raise ValueError(f"Aseguradora desconocida: '{self.aseguradora_id}'")

            # 3. Login Inicial
            self.progreso_update.emit(f"Realizando login inicial en {modulo_nombre}...")
            login_ok, login_log = login_func(driver, wait)
            self.progreso_update.emit(login_log)
            if not login_ok:
                self.error_critico.emit(f"Fallo en login inicial.")
                return

            # --- 4. NAVEGAR A INICIO UNA VEZ DESPUÉS DEL LOGIN ---
            self.progreso_update.emit(
                f"Navegando a página inicial de formularios ({modulo_nombre})..."
            )
            # navegar_inicio_func retorna (True/False, logs_str)
            nav_inicio_ok, nav_inicio_log = navegar_inicio_func(driver, wait)
            self.progreso_update.emit(nav_inicio_log)
            if not nav_inicio_ok:
                self.error_critico.emit(
                    f"Fallo CRÍTICO al navegar a página de inicio post-login."
                )
                # Considerar cerrar driver aquí si esto falla
                # if driver: cerrar_driver(driver)
                return  # Detener proceso
            # --- FIN NAVEGACIÓN INICIAL ---

            # 5. Encontrar y ORDENAR NUMÉRICAMENTE subcarpetas
            self.progreso_update.emit("Buscando y ordenando subcarpetas...")
            try:
                subcarpetas_temp = [
                    d for d in self.carpeta_contenedora_path.iterdir() if d.is_dir()
                ]

                def try_get_int_name(path_obj):
                    try:
                        return int(path_obj.name)
                    except ValueError:
                        return float("inf")  # No numéricos al final

                subcarpetas = sorted(subcarpetas_temp, key=try_get_int_name)
                self.progreso_update.emit("  -> Subcarpetas ordenadas.")
            except Exception as e_list:
                self.error_critico.emit(
                    f"Error listando/ordenando subcarpetas: {e_list}"
                )
                return

            if not subcarpetas:
                self.progreso_update.emit(
                    "No se encontraron subcarpetas para procesar."
                )
                self.finalizado.emit(0, 0, 0, 0)
                return

            total_carpetas = len(subcarpetas)
            self.progreso_update.emit(
                f"Se procesarán {total_carpetas} subcarpetas (ordenadas)."
            )
            self.progreso_update.emit("=" * 40)

            # 6. Procesar Subcarpetas (Bucle FOR)
            for i, subfolder_path in enumerate(subcarpetas):
                if self._detener:
                    self.progreso_update.emit("--- PROCESO DETENIDO ---")
                    break

                subfolder_name = subfolder_path.name
                self.progreso_update.emit(
                    f"\n>>> Procesando Carpeta {i+1}/{total_carpetas}: '{subfolder_name}'"
                )

                # Llamar a la función específica (ya no necesita verificar página)
                # Retorna: (estado_str, codigo_radicado | None, logs_str)
                estado_carpeta, codigo_radicado, log_carpeta = funcion_procesar_carpeta(
                    driver, wait, subfolder_path, subfolder_name
                )
                self.progreso_update.emit(log_carpeta)

                # Interpretar estado
                if estado_carpeta == ESTADO_EXITO:
                    carpetas_exitosas += 1
                    # Guardar resultado exitoso
                    try:
                        # Re-validar para obtener código de factura final
                        # Asegúrate que la ruta sea correcta si la carpeta es 'nucleo'
                        from Core.utilidades import encontrar_y_validar_pdfs

                        codigo_factura_final, _, _ = encontrar_y_validar_pdfs(
                            subfolder_path, subfolder_name
                        )
                    except Exception as e_val_rep:
                        self.progreso_update.emit(
                            f"ADVERTENCIA: No se pudo re-validar PDF para factura final en '{subfolder_name}': {e_val_rep}"
                        )
                        codigo_factura_final = "Error re-validación"
                    resultado = {
                        "subcarpeta": subfolder_name,
                        "factura": codigo_factura_final or "N/A",
                        "radicado": codigo_radicado or "No Extraído",
                        "rad_pdf_path": str(subfolder_path / "RAD.pdf"),
                    }
                    self.resultados_exitosos.append(resultado)
                elif estado_carpeta == ESTADO_FALLO:
                    carpetas_fallidas += 1
                    self.progreso_update.emit(
                        f"--- ERROR procesando: '{subfolder_name}' ---"
                    )
                elif estado_carpeta == ESTADO_OMITIDO_RADICADO:
                    carpetas_omitidas_rad += 1
                    self.progreso_update.emit(
                        f"--- OMITIDA (RAD): '{subfolder_name}' ---"
                    )
                elif estado_carpeta == ESTADO_OMITIDO_DUPLICADA:
                    carpetas_omitidas_dup += 1
                    self.progreso_update.emit(
                        f"--- OMITIDA (Dup): '{subfolder_name}' ---"
                    )
                else:  # Estado desconocido
                    self.progreso_update.emit(
                        f"ADVERTENCIA: Estado desconocido '{estado_carpeta}' para '{subfolder_name}'"
                    )
                    carpetas_fallidas += 1

                self.progreso_update.emit("-" * 40)
            # --- FIN BUCLE FOR ---

        except (
            ImportError,
            NotImplementedError,
            ValueError,
            WebDriverException,
        ) as err:
            # Capturar errores de configuración, módulo, WebDriver (incluye conexión)
            error_msg = (
                f"ERROR CRÍTICO ({type(err).__name__}): {err}\nEl proceso se detendrá."
            )
            self.progreso_update.emit(error_msg)
            traceback.print_exc()  # Log detallado
            self.error_critico.emit(error_msg)  # Notificar a GUI
            # Guardar progreso JSON antes de salir
            try:
                ruta_resultados_json = (
                    self.carpeta_contenedora_path / "resultados_automatizacion.json"
                )
                if self.resultados_exitosos:
                    with open(ruta_resultados_json, "w", encoding="utf-8") as f:
                        json.dump(self.resultados_exitosos, f, indent=4)
                    self.progreso_update.emit(
                        f"Resultados parciales guardados en {ruta_resultados_json.name}"
                    )
            except Exception as ej:
                self.progreso_update.emit(f"Error guardando JSON parcial: {ej}")
            # No emitir finalizado normal, ya se emitió error_critico

        except Exception as e_main:
            # Capturar cualquier otro error inesperado
            error_msg = f"!!! ERROR CRÍTICO INESPERADO EN AUTOMATIZACIÓN !!!\n{traceback.format_exc()}"
            self.progreso_update.emit(error_msg)
            self.error_critico.emit("Ocurrió un error crítico inesperado.")
            # Guardar progreso JSON antes de salir
            try:
                ruta_resultados_json = (
                    self.carpeta_contenedora_path / "resultados_automatizacion.json"
                )
                if self.resultados_exitosos:
                    with open(ruta_resultados_json, "w", encoding="utf-8") as f:
                        json.dump(self.resultados_exitosos, f, indent=4)
                    self.progreso_update.emit(
                        f"Resultados parciales guardados en {ruta_resultados_json.name}"
                    )
            except Exception as ej:
                self.progreso_update.emit(f"Error guardando JSON parcial: {ej}")
            # No emitir finalizado normal

        finally:
            # --- Guardar JSON (SOLO si no hubo error crítico que ya lo guardó) ---
            # Verificar si ya se emitió error crítico (no tenemos flag directo, pero podemos verificar si driver existe)
            if (
                "err" not in locals() and "e_main" not in locals()
            ):  # Si no hubo excepción grave capturada arriba
                ruta_resultados_json = (
                    self.carpeta_contenedora_path / "resultados_automatizacion.json"
                )
                try:
                    if self.resultados_exitosos:
                        self.progreso_update.emit(
                            f"\nGuardando {len(self.resultados_exitosos)} resultados en {ruta_resultados_json.name}..."
                        )
                        with open(ruta_resultados_json, "w", encoding="utf-8") as f:
                            json.dump(self.resultados_exitosos, f, indent=4)
                        self.progreso_update.emit("Resumen de resultados guardado.")
                    else:
                        self.progreso_update.emit(
                            "\nNo hubo resultados exitosos para guardar."
                        )
                except Exception as e:
                    self.progreso_update.emit(f"ADVERTENCIA: No se guardó JSON: {e}")

            # --- Cerrar driver ---
            if driver:
                # Reimportar por si acaso hubo error antes
                try:
                    from .utilidades import cerrar_driver
                except ImportError:
                    print("Error reimportando cerrar_driver")
                else:
                    driver_close_log = cerrar_driver(driver)
                    self.progreso_update.emit("\n" + driver_close_log)

            # --- Resumen Final ---
            # Solo emitir finalizado si no hubo error crítico que ya terminó el flujo
            if "err" not in locals() and "e_main" not in locals():
                end_time = time.time()
                total_time = end_time - start_time
                summary_msg = f"\n{'='*40}\n--- FIN AUTOMATIZACIÓN ---\n"
                summary_msg += f"Resultados:\n  - Éxitos: {carpetas_exitosas}\n  - Errores: {carpetas_fallidas}\n"
                summary_msg += f"  - Omitidas (RAD): {carpetas_omitidas_rad}\n  - Omitidas (Dup): {carpetas_omitidas_dup}\n"
                # summary_msg += f"  - Fallo tras Reintento: {0}\n" # Ya no aplica
                summary_msg += f"Tiempo Total: {total_time:.2f} seg ({total_time/60:.2f} min)\n{'='*40}"
                self.progreso_update.emit(summary_msg)
                # Emitir señal finalizado con solo exitos y fallos (o ajustar si necesitas más info)
                self.finalizado.emit(
                    carpetas_exitosas,
                    carpetas_fallidas,
                    carpetas_omitidas_rad,
                    carpetas_omitidas_dup,
                )
