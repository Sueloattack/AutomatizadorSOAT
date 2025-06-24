# AutomatizadorSOAT/nucleo/utilidades.py
import os
import re
import time
import sys
import traceback
from pathlib import Path
import shutil

# Dependencias de Selenium (asegúrate de que estén en requirements.txt)
try:
    from selenium import webdriver
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import WebDriverException
except ImportError:
    print("ERROR CRÍTICO: Faltan dependencias de Selenium.")
    raise ImportError("Faltan dependencias de Selenium. Ejecuta: pip install selenium")

# Dependencia de Pillow (asegúrate de que esté en requirements.txt)
try:
    from PIL import Image
except ImportError:
    print("ERROR CRÍTICO: Falta dependencia de Pillow.")
    raise ImportError("Falta dependencia de Pillow. Ejecuta: pip install Pillow")


def resource_path(relative_path):
    """Obtiene la ruta absoluta al recurso, funciona para desarrollo y PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    path_to_resource = os.path.join(base_path, relative_path)
    return path_to_resource


def obtener_ruta_driver():
    """
    Determina la ruta del msedgedriver.exe usando EXCLUSIVAMENTE webdriver-manager.
    """
    print("Buscando WebDriver usando webdriver-manager...")
    try:
        from webdriver_manager.microsoft import EdgeChromiumDriverManager

        path_wdm = EdgeChromiumDriverManager().install()
        print(f"  WebDriver gestionado por webdriver-manager: {path_wdm}")
        return Path(path_wdm)
    except ImportError:
        error_msg = "  ERROR CRÍTICO: Falta 'webdriver-manager'. Instala: pip install webdriver-manager"
        print(error_msg)
        return None
    except Exception as e_wdm:
        error_msg = f"  ERROR al usar webdriver-manager: {e_wdm}"
        print(error_msg)
        traceback.print_exc()
        return None


def configurar_driver(headless=True):
    """Configura e inicia el WebDriver de Edge."""
    ruta_driver = obtener_ruta_driver()
    if not ruta_driver:
        return None, None, "ERROR: No se pudo obtener la ruta del WebDriver."

    service = None

    try:
        edge_options = EdgeOptions()
        if headless:
            edge_options.add_argument("--headless")
            edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--window-size=1920,1080")
        edge_options.add_argument("--start-maximized")
        edge_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        edge_options.add_argument("--disable-notifications")
        edge_options.add_argument("--disable-popup-blocking")
        edge_options.add_argument("--log-level=3")
        edge_options.add_argument("--disable-software-rasterizer")
        edge_options.add_argument("--disable-extensions")  # Aún puede ser útil

        service = EdgeService(executable_path=str(ruta_driver))
        driver = webdriver.Edge(service=service, options=edge_options)
        wait = WebDriverWait(driver, 35)

        modo = "headless" if headless else "con interfaz"
        log_msg = f"WebDriver iniciado ({modo}) usando driver gestionado (perfil por defecto/gestionado por driver)."
        return driver, wait, log_msg

    except WebDriverException as e:
        error_msg = f"ERROR CRÍTICO al iniciar WebDriver: {e}\nVerifique compatibilidad/permisos."
        traceback.print_exc()
        if service:
            try:
                service.stop()
            except Exception:
                pass
        return None, None, error_msg
    except Exception as e:
        error_msg = f"ERROR inesperado configuración driver: {e}"
        traceback.print_exc()
        if service:
            try:
                service.stop()
            except Exception:
                pass
        return None, None, error_msg


def cerrar_driver(driver):
    """Cierra el navegador WebDriver de forma segura (SIN limpiar perfil explícitamente)."""
    # dir_perfil_a_limpiar = getattr(driver, 'user_data_dir', None) # <-- ELIMINAR
    if driver:
        log_msg = "Cerrando navegador WebDriver..."
        try:
            driver.quit()
            log_msg += "\nNavegador cerrado correctamente."
        except Exception as e_quit:
            log_msg += f"\nError al cerrar el navegador: {e_quit}"
        # --- ELIMINADA LA LLAMADA A _limpiar_directorio_perfil ---
        # _limpiar_directorio_perfil(dir_perfil_a_limpiar)
        # -------------------------------------------------------
        print(log_msg)
        return log_msg
    else:
        no_driver_msg = "Intento de cerrar driver, pero no estaba iniciado."
        print(no_driver_msg)
        # _limpiar_directorio_perfil(dir_perfil_a_limpiar) # <-- ELIMINAR
        return no_driver_msg


def encontrar_y_validar_pdfs(
    subfolder_path, nombre_subcarpeta
) -> tuple[str | None, Path | None, str]:
    """
    Busca PDF tipo 1 ([PREFIJO_CONOCIDO][NUMERO].pdf) y
    PDF tipo 2 (...[PREFIJO_LETRAS]_[NUMERO_DIGITOS]_LA PREVISORA S.A.(opcional).pdf).
    Compara códigos limpios (PREFIJO+NUMERO). Si difieren, renombra pdf1.
    Devuelve (codigo_limpio_pdf2, ruta_final_pdf1, mensaje_log).
    """
    subfolder_path = Path(subfolder_path).resolve()

    # --- PATRÓN PDF1 (Estricto para PREFIJO_CONOCIDO + NUMERO) ---
    pdf1_pattern = re.compile(r"^(FECR|COEX|FERD|FERR|FCR)(\d+)\.pdf$", re.IGNORECASE)
    # Ejemplo: FECR304039.pdf -> Grupo1=FECR, Grupo2=304039

    # --- PATRÓN PDF2 (Más preciso para el final) ---
    # .*?                             - Cualquier cosa al inicio (no codicioso)
    # ([A-Z]+)_(\d+)                  - Grupo 1 (Prefijo), Grupo 2 (Número)
    # _LA PREVISORA S\.A\.            - Literal (puntos escapados)
    # (?:\s*\(\d+\))?                 - Grupo opcional SIN captura para " (NUMERO)"
    #                                   \s*      -> cero o más espacios
    #                                   \(\d+\)  -> (un número)
    #                                   ?        -> hace todo el grupo opcional
    # \.pdf$                          - Termina con .pdf
    pdf2_pattern = re.compile(
        r".*?([A-Z]+)_(\d+)_LA PREVISORA S\.A\.?(\s*\(\d+\))?\.pdf$", re.IGNORECASE
    )
    # Ejemplos que debe capturar:
    # FECR_310575_LA PREVISORA S.A..pdf   -> Grupo1=FECR, Grupo2=310575
    # ALGO_FECR_300586_LA PREVISORA S.A. (1).pdf -> Grupo1=FECR, Grupo2=300586

    pdf1_match_info = None
    archivos_candidatos_pdf2 = []

    log_prefix = f"[{nombre_subcarpeta}] "
    log_messages = [f"{log_prefix}Validando PDFs (Patrones v3)..."]

    try:
        if not subfolder_path.is_dir():
            return None, None, f"{log_prefix}ERROR: Subcarpeta no existe."

        for item in subfolder_path.iterdir():
            if item.is_file():
                filename = item.name
                log_messages.append(f"{log_prefix}  Analizando: {filename}")
                if filename.upper() == "RAD.PDF":
                    continue

                # Buscar pdf1
                if not pdf1_match_info:  # Tomar solo el primero
                    match1 = pdf1_pattern.match(filename)
                    if match1:
                        codigo1 = f"{match1.group(1).upper()}{match1.group(2)}"
                        pdf1_match_info = {
                            "path": item,
                            "filename": filename,
                            "codigo": codigo1,
                        }
                        log_messages.append(
                            f"{log_prefix}    -> Coincide PDF Tipo 1 (Código: {codigo1})"
                        )

                # Buscar pdf2
                match2 = pdf2_pattern.match(filename)
                if match2:
                    prefijo2 = match2.group(1).upper()
                    numero2 = match2.group(2)
                    codigo_limpio2 = f"{prefijo2}{numero2}"
                    # Guardar si tiene " (N)" para priorizar el que no lo tiene
                    tiene_sufijo_numerico = bool(
                        re.search(r"\s*\(\d+\)\.pdf$", filename, re.IGNORECASE)
                    )
                    archivos_candidatos_pdf2.append(
                        {
                            "path": item,
                            "filename": filename,
                            "codigo_limpio": codigo_limpio2,
                            "tiene_sufijo": tiene_sufijo_numerico,
                        }
                    )
                    log_messages.append(
                        f"{log_prefix}    -> Coincide PDF Tipo 2 (Código limpio: {codigo_limpio2}, Sufijo: {tiene_sufijo_numerico})"
                    )

        # Validación Post-Búsqueda
        if not pdf1_match_info:
            return (
                None,
                None,
                f"{log_prefix}ERROR: No se encontró PDF tipo 1 (ej: FECR123.pdf).",
            )
        if not archivos_candidatos_pdf2:
            return (
                None,
                None,
                f"{log_prefix}ERROR: No se encontró PDF tipo 2 (ej: ..._LA PREVISORA S.A.(opcional).pdf).",
            )

        # --- Selección de PDF2 (Priorizar el que NO tiene sufijo numérico) ---
        pdf2_seleccionado = None
        if len(archivos_candidatos_pdf2) == 1:
            pdf2_seleccionado = archivos_candidatos_pdf2[0]
        else:  # Múltiples candidatos
            log_messages.append(
                f"{log_prefix}ADVERTENCIA: Múltiples candidatos para PDF Tipo 2. Priorizando sin sufijo numérico..."
            )
            sin_sufijo = [d for d in archivos_candidatos_pdf2 if not d["tiene_sufijo"]]
            if sin_sufijo:
                pdf2_seleccionado = sin_sufijo[0]  # Tomar el primero sin sufijo
                if len(sin_sufijo) > 1:
                    log_messages.append(
                        f"{log_prefix}  -> Múltiples sin sufijo. Usando: {pdf2_seleccionado['filename']}"
                    )
            else:  # Todos tienen sufijo, tomar el primero de la lista original
                pdf2_seleccionado = archivos_candidatos_pdf2[0]
                log_messages.append(
                    f"{log_prefix}  -> Todos los candidatos tienen sufijo. Usando: {pdf2_seleccionado['filename']}"
                )
        # --- Fin Selección PDF2 ---

        pdf1_path_original = pdf1_match_info["path"]
        codigo_pdf1 = pdf1_match_info["codigo"]
        codigo_limpio_pdf2 = pdf2_seleccionado["codigo_limpio"]
        log_messages.append(
            f"{log_prefix}  PDF 1 Final: {pdf1_path_original.name} (Código: {codigo_pdf1})"
        )
        log_messages.append(
            f"{log_prefix}  PDF 2 Final: {pdf2_seleccionado['filename']} (Código limpio: {codigo_limpio_pdf2})"
        )

        # --- Comparación y Renombrado (Lógica SIN CAMBIOS respecto a la última versión) ---
        pdf_principal_a_cargar_path = pdf1_path_original
        log_messages.append(
            f"{log_prefix}Comparando Código PDF1 ('{codigo_pdf1}') con Código Limpio PDF2 ('{codigo_limpio_pdf2}')..."
        )
        if codigo_pdf1 != codigo_limpio_pdf2:
            log_messages.append(f"{log_prefix}  -> ¡Discrepancia detectada!")
            nuevo_nombre_para_pdf = f"{codigo_limpio_pdf2}.pdf"
            nuevo_pdf1_path = subfolder_path / nuevo_nombre_para_pdf
            log_messages.append(
                f"{log_prefix}     Se renombrará '{pdf1_path_original.name}' a '{nuevo_nombre_para_pdf}'."
            )
            if (
                nuevo_pdf1_path.exists()
                and nuevo_pdf1_path.resolve() != pdf1_path_original.resolve()
            ):
                error_msg = f"{log_prefix}ERROR: Ya existe archivo destino '{nuevo_nombre_para_pdf}'. Renombrado cancelado."
                log_messages.append(error_msg)
                return None, None, "\n".join(log_messages)
            if pdf1_path_original.name.lower() != nuevo_nombre_para_pdf.lower():
                try:
                    pdf1_path_original.rename(nuevo_pdf1_path)
                    log_messages.append(
                        f"{log_prefix}     Renombrado realizado con éxito."
                    )
                    pdf_principal_a_cargar_path = nuevo_pdf1_path
                except OSError as e_rename:
                    error_msg = f"{log_prefix}ERROR al renombrar: {e_rename}"
                    log_messages.append(error_msg)
                    return None, None, "\n".join(log_messages)
            else:
                log_messages.append(
                    f"{log_prefix}     Archivo ya tiene el nombre destino. No se renombra."
                )
                pdf_principal_a_cargar_path = pdf1_path_original
        else:
            log_messages.append(
                f"{log_prefix}  -> Códigos coinciden. No se requiere renombrar."
            )
            pdf_principal_a_cargar_path = pdf1_path_original
        # --- Fin Comparación y Renombrado ---

        # --- Devolución ---
        codigo_a_usar_en_formulario = codigo_limpio_pdf2
        ruta_pdf_a_cargar = pdf_principal_a_cargar_path
        if not ruta_pdf_a_cargar or not ruta_pdf_a_cargar.is_file():
            error_msg = f"{log_prefix}ERROR: Ruta final PDF a cargar inválida: {ruta_pdf_a_cargar}"
            log_messages.append(error_msg)
            return None, None, "\n".join(log_messages)
        log_messages.append(
            f"{log_prefix}Código final para factura: {codigo_a_usar_en_formulario}"
        )
        log_messages.append(
            f"{log_prefix}Ruta PDF principal a cargar: {ruta_pdf_a_cargar.name}"
        )
        return codigo_a_usar_en_formulario, ruta_pdf_a_cargar, "\n".join(log_messages)

    except Exception as e:
        error_msg = f"{log_prefix}Error inesperado procesando PDFs: {e}"
        log_messages.append(error_msg)
        traceback.print_exc()
        return None, None, "\n".join(log_messages)
