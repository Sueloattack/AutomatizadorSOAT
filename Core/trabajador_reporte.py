# AutomatizadorSOAT/nucleo/trabajador_reporte.py
import os
import time
import traceback
from pathlib import Path
import datetime
from PySide6 import QtCore
import json  # Para leer resultados

# Ya NO necesitamos importar utilidades aquí para validar PDFs
# from .utilidades import encontrar_y_validar_pdfs

# Importar generador de PDF
# Asegúrate que la ruta sea correcta si la carpeta es 'nucleo'
from .generador_reportes import crear_reporte_pdf


class TrabajadorReporte(QtCore.QObject):
    """
    Clase QObject que genera el reporte PDF leyendo los resultados
    desde 'resultados_automatizacion.json'.
    """

    # --- Señales ---
    progreso_update = QtCore.Signal(str)
    finalizado = QtCore.Signal(bool, str)  # (éxito, mensaje/ruta_pdf)
    error_critico = QtCore.Signal(str)

    def __init__(self, carpeta_contenedora):
        super().__init__()
        self.carpeta_contenedora_path = Path(carpeta_contenedora).resolve()

    @QtCore.Slot()
    def run_report_generation(self):
        """Método principal que ejecuta la generación del reporte."""
        self.progreso_update.emit("--- INICIANDO GENERACIÓN DE REPORTE ---")
        self.progreso_update.emit(
            f"Carpeta a reportar: {self.carpeta_contenedora_path}"
        )

        datos_para_tabla = []
        encabezados = [
            "Código Subcarpeta",
            "Número Factura",
            "Código Radicado",
            "Fecha Creación RAD",
        ]
        datos_para_tabla.append(encabezados)
        carpetas_procesadas_reporte = 0
        start_time = time.time()

        # --- LEER RESULTADOS DEL JSON ---
        ruta_resultados_json = (
            self.carpeta_contenedora_path / "resultados_automatizacion.json"
        )
        resultados_automatizacion = []
        try:
            self.progreso_update.emit(
                f"Leyendo archivo de resultados: {ruta_resultados_json.name}..."
            )
            if not ruta_resultados_json.is_file():
                msg = (
                    "ERROR: No se encontró el archivo 'resultados_automatizacion.json'. "
                    "Asegúrese de ejecutar la automatización primero en esta carpeta."
                )
                self.progreso_update.emit(msg)
                self.finalizado.emit(False, msg)
                return

            with open(ruta_resultados_json, "r", encoding="utf-8") as f_json:
                resultados_automatizacion = json.load(f_json)

            if not isinstance(resultados_automatizacion, list):
                raise TypeError("El archivo JSON no contiene una lista de resultados.")

            if not resultados_automatizacion:
                msg = "El archivo de resultados está vacío o no contiene datos."
                self.progreso_update.emit(msg)
                self.finalizado.emit(False, "No se generó reporte: " + msg)
                return

            self.progreso_update.emit(
                f"Se encontraron {len(resultados_automatizacion)} resultados exitosos para reportar."
            )
            self.progreso_update.emit("=" * 40)

        except json.JSONDecodeError as e_json_dec:
            msg = f"Error al decodificar el archivo JSON '{ruta_resultados_json.name}': {e_json_dec}"
            self.progreso_update.emit(msg)
            self.error_critico.emit(msg)
            self.finalizado.emit(False, msg)
            return
        except Exception as e_json:
            msg = f"Error leyendo el archivo JSON de resultados '{ruta_resultados_json.name}': {e_json}"
            self.progreso_update.emit(msg)
            self.error_critico.emit(msg)
            self.finalizado.emit(False, msg)
            return
        # --- FIN LECTURA JSON ---

        try:
            # Iterar sobre los RESULTADOS leídos del JSON
            for resultado in resultados_automatizacion:
                # Extraer datos del diccionario con valores por defecto seguros
                subfolder_name = resultado.get("subcarpeta", "N/A")
                codigo_factura = resultado.get("factura", "N/A")
                codigo_radicado = resultado.get(
                    "radicado", "N/A"
                )  # Leer radicado del JSON
                rad_pdf_path_str = resultado.get("rad_pdf_path")
                fecha_creacion = "N/A"  # Fecha por defecto

                self.progreso_update.emit(
                    f"\nAñadiendo al reporte: '{subfolder_name}'..."
                )
                self.progreso_update.emit(f"  - Factura: {codigo_factura}")
                self.progreso_update.emit(
                    f"  - Radicado: {codigo_radicado}"
                )  # Mostrar radicado leído

                # Obtener fecha del RAD.pdf usando la ruta guardada
                if rad_pdf_path_str:
                    rad_pdf_path = Path(rad_pdf_path_str)
                    if rad_pdf_path.is_file():
                        try:
                            timestamp_modificacion = rad_pdf_path.stat().st_mtime
                            fecha_obj = datetime.datetime.fromtimestamp(
                                timestamp_modificacion
                            )
                            fecha_creacion = fecha_obj.strftime("%d/%m/%Y")
                            self.progreso_update.emit(
                                f"  - Fecha RAD: {fecha_creacion}"
                            )
                        except Exception as e_date:
                            self.progreso_update.emit(
                                f"  - Error obteniendo fecha de {rad_pdf_path.name}: {e_date}"
                            )
                            fecha_creacion = "Error fecha"
                    else:
                        self.progreso_update.emit(
                            f"  - Advertencia: RAD.pdf no encontrado en ruta guardada: {rad_pdf_path_str}"
                        )
                        fecha_creacion = "N/A (PDF no hallado)"
                else:
                    self.progreso_update.emit(
                        "  - Advertencia: No se encontró ruta de RAD.pdf en los resultados."
                    )
                    fecha_creacion = "N/A (Sin ruta)"

                datos_para_tabla.append(
                    [
                        subfolder_name,
                        codigo_factura,
                        codigo_radicado,  # Usar el radicado leído del JSON
                        fecha_creacion,
                    ]
                )
                carpetas_procesadas_reporte += 1

            # --- Generar el PDF ---
            self.progreso_update.emit("\n" + "=" * 40)
            if carpetas_procesadas_reporte > 0:
                self.progreso_update.emit(
                    f"Preparando generación de REPORTE.pdf con {carpetas_procesadas_reporte} entradas..."
                )
                nombre_carpeta_padre = self.carpeta_contenedora_path.name
                ruta_salida_pdf = self.carpeta_contenedora_path / "REPORTE.pdf"

                # Llamar a la función que crea el PDF
                pdf_ok, pdf_msg = crear_reporte_pdf(
                    ruta_salida_pdf, nombre_carpeta_padre, datos_para_tabla
                )

                self.progreso_update.emit(pdf_msg)
                # Emitir finalizado con el resultado de la creación del PDF
                self.finalizado.emit(
                    pdf_ok,
                    (
                        pdf_msg
                        if not pdf_ok
                        else f"Reporte guardado en: {ruta_salida_pdf}"
                    ),
                )
            else:
                # Si el JSON estaba vacío o no tenía entradas válidas
                self.progreso_update.emit(
                    "No se procesaron resultados válidos del JSON para incluir en el reporte."
                )
                self.finalizado.emit(
                    False,
                    "No se generó reporte: No se procesaron resultados válidos del archivo JSON.",
                )

        except Exception as e_main:
            error_msg = f"!!! ERROR CRÍTICO INESPERADO GENERANDO REPORTE !!!\n{traceback.format_exc()}"
            self.progreso_update.emit(error_msg)
            self.error_critico.emit(
                "Ocurrió un error crítico inesperado al generar el reporte."
            )
            self.finalizado.emit(False, "Error crítico durante generación de reporte.")

        finally:
            end_time = time.time()
            total_time = end_time - start_time
            summary_msg = "\n" + "=" * 40 + "\n"
            summary_msg += "--- FIN GENERACIÓN REPORTE ---\n"
            summary_msg += f"Tiempo Total: {total_time:.2f} seg\n"
            summary_msg += "=" * 40
            self.progreso_update.emit(summary_msg)
            # La señal 'finalizado' se emite dentro del bloque try/except
