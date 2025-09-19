# AutomatizadorSOAT/nucleo/utilidades.py
from datetime import datetime
import os
import re
import sys
from time import time
import traceback
from pathlib import Path
from email.header import decode_header
from PyPDF2 import PdfWriter, PdfReader
import io
import json
import tempfile
import subprocess



from Configuracion.constantes import AXASOAT_EMAIL_SENDER, EMAIL_APP_PASSWORD, EMAIL_IMAP_SERVER, EMAIL_PROCESSED_FOLDER, EMAIL_SEARCH_DELAY_SECONDS, EMAIL_SEARCH_RETRIES, EMAIL_USER_ADDRESS

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

# Reemplaza la función en utilidades.py
def encontrar_y_validar_pdfs(
    subfolder_path: Path, nombre_subcarpeta: str, nombre_aseguradora_en_pdf: str
) -> tuple[str | None, Path | None, str]:
    """
    Busca y valida los PDFs de Glosa. Ahora es más flexible: puede proceder
    solo con la carta si la respuesta no se encuentra.
    """
    subfolder_path = subfolder_path.resolve()
    log_prefix = f"[{nombre_subcarpeta}] "
    log_messages = [f"{log_prefix}Validando PDFs (Lógica Flexible)..."]
    
    ignorar_carta_faltante = "sin carta glosa" in nombre_subcarpeta.lower()
    if ignorar_carta_faltante: log_messages.append(f"{log_prefix}  -> DETECTADO: 'sin carta glosa'.")

    respuesta_glosa_pattern = re.compile(r"^(FECR|COEX|FERD|FERR|FCR)(\d+)\.pdf$", re.IGNORECASE)
    nombre_escapado = re.escape(nombre_aseguradora_en_pdf)
    carta_glosa_pattern = re.compile(rf".*?([A-Z]+)[_-](\d+)[_-]{nombre_escapado}.*?\.pdf$", re.IGNORECASE)

    respuesta_glosa_info = None
    candidatos_carta_glosa = []

    try:
        # --- Búsqueda ---
        for item in subfolder_path.iterdir():
            if not item.is_file(): continue
            filename = item.name
            if filename.upper() == "RAD.PDF": continue

            if not respuesta_glosa_info:
                match_respuesta = respuesta_glosa_pattern.match(filename)
                if match_respuesta:
                    codigo = f"{match_respuesta.group(1).upper()}{match_respuesta.group(2)}"
                    respuesta_glosa_info = {"path": item, "filename": filename, "codigo": codigo}
                    log_messages.append(f"{log_prefix}  -> Encontrada Respuesta Glosa: '{filename}'")
            
            match_carta = carta_glosa_pattern.search(filename)
            if match_carta:
                codigo = f"{match_carta.group(1).upper()}{match_carta.group(2)}"
                candidatos_carta_glosa.append({"path": item, "filename": filename, "codigo_limpio": codigo})
                log_messages.append(f"{log_prefix}  -> Encontrada Carta Glosa: '{filename}'")

        # --- NUEVA LÓGICA DE VALIDACIÓN FLEXIBLE ---
        
        # Primero, verificar que al menos UNO de los dos se haya encontrado.
        if not respuesta_glosa_info and not candidatos_carta_glosa:
            return None, None, f"{log_prefix}ERROR: No se encontró NI Respuesta Glosa NI Carta Glosa."
        
        # Ahora, decidimos cuál archivo y código usar.
        if respuesta_glosa_info:
            # CASO 1: Tenemos la respuesta. Es nuestra prioridad para subir.
            path_a_cargar = respuesta_glosa_info["path"]
            codigo_de_respuesta = respuesta_glosa_info["codigo"]
            log_messages.append(f"{log_prefix}  -> Archivo a cargar: {path_a_cargar.name}")

            if candidatos_carta_glosa:
                # Subcaso 1.1: Tenemos ambos. El código de la carta manda.
                codigo_final = candidatos_carta_glosa[0]["codigo_limpio"]
                log_messages.append(f"{log_prefix}  -> Ambos archivos presentes. Código final se toma de la Carta: '{codigo_final}'")
            else:
                # Subcaso 1.2: Solo tenemos la respuesta. Su código es el que vale.
                codigo_final = codigo_de_respuesta
                log_messages.append(f"{log_prefix}  -> Solo Respuesta encontrada. Código final se toma de la Respuesta: '{codigo_final}'")
        else:
            # CASO 2: NO tenemos la respuesta, pero SÍ la carta.
            log_messages.append(f"{log_prefix}ADVERTENCIA: No se encontró Respuesta Glosa, se usará la Carta Glosa en su lugar.")
            carta_seleccionada = candidatos_carta_glosa[0]
            path_a_cargar = carta_seleccionada["path"]
            codigo_final = carta_seleccionada["codigo_limpio"]
            log_messages.append(f"{log_prefix}  -> Archivo a cargar: {path_a_cargar.name}")
            log_messages.append(f"{log_prefix}  -> Código final se toma de la Carta: '{codigo_final}'")

        return codigo_final, path_a_cargar, "\n".join(log_messages)

    except Exception as e:
        return None, None, f"{log_prefix}Error inesperado: {e}"
    
def encontrar_documentos_facturacion(subfolder_path: Path, nombre_subcarpeta: str) -> tuple[str | None, dict[str, Path] | None, str]:
    """
    Busca los documentos necesarios para un radicado de Facturación.

    Busca 3 archivos clave por sus prefijos:
    1. FACTURA_... .pdf
    2. FURIPS_... .pdf
    3. HC_... .pdf

    Extrae el código de la factura (ej: FECR309222) de CUALQUIERA de los nombres de archivo.

    Devuelve:
    - El código de la factura a usar en el formulario.
    - Un diccionario con las rutas a los 3 archivos encontrados.
    - Un log del proceso.
    """
    subfolder_path = subfolder_path.resolve()
    log_prefix = f"[{nombre_subcarpeta}] "
    log_messages = [f"{log_prefix}Buscando documentos de Facturación..."]

    documentos_encontrados = {}
    codigo_factura = None

    # Patrón para extraer el código de factura, ej: de 'FACTURA_FECR309222.pdf'
    pattern_codigo = re.compile(r"_(FECR|COEX|FERD|FERR|FCR)(\d+)\.pdf$", re.IGNORECASE)

    try:
        if not subfolder_path.is_dir():
            return None, None, f"{log_prefix}ERROR: Subcarpeta no existe."

        for item in subfolder_path.iterdir():
            if not item.is_file(): continue
            
            filename_upper = item.name.upper()
            
            if filename_upper.startswith("FACTURA_"):
                documentos_encontrados["factura"] = item
                log_messages.append(f"{log_prefix}  -> Encontrada FACTURA: {item.name}")
            elif filename_upper.startswith("FURIPS_"):
                documentos_encontrados["furips"] = item
                log_messages.append(f"{log_prefix}  -> Encontrados FURIPS: {item.name}")
            elif filename_upper.startswith("HC_"):
                documentos_encontrados["hc"] = item
                log_messages.append(f"{log_prefix}  -> Encontrada Historia Clínica: {item.name}")

            # Intentar extraer el código de factura de cualquier archivo
            if not codigo_factura:
                match = pattern_codigo.search(item.name)
                if match:
                    codigo_factura = f"{match.group(1)}{match.group(2)}"
                    log_messages.append(f"{log_prefix}  -> Código de factura extraído: {codigo_factura}")
        
        # Validación
        documentos_requeridos = ["factura", "furips", "hc"]
        faltantes = [doc for doc in documentos_requeridos if doc not in documentos_encontrados]
        if faltantes:
            return None, None, f"{log_prefix}ERROR: Faltan documentos requeridos: {', '.join(faltantes)}"
        if not codigo_factura:
            return None, None, f"{log_prefix}ERROR: No se pudo extraer el código de factura de ningún archivo."
            
        return codigo_factura, documentos_encontrados, "\n".join(log_messages)

    except Exception as e:
        return None, None, f"{log_prefix}Error inesperado: {e}"
    
def consolidar_radicados_pdf(carpeta_contenedora: Path, nombre_salida: str = "RADICADO.pdf") -> tuple[bool, str]:
    """
    Busca todos los archivos RAD.pdf individuales dentro de las subcarpetas,
    los une en un solo archivo PDF maestro y elimina los archivos individuales.

    Args:
        carpeta_contenedora: La carpeta principal (ej. 'CUENTA 66553')
        nombre_salida: El nombre del archivo PDF unificado final.

    Returns:
        (éxito, mensaje_log)
    """
    logs = [f"\n--- Iniciando Consolidación de Radicados en: {carpeta_contenedora.name} ---"]
    pdfs_a_unir = []

    # 1. Buscar recursivamente todos los RAD.pdf en las subcarpetas
    for subfolder in carpeta_contenedora.iterdir():
        if subfolder.is_dir():
            rad_file = subfolder / "RAD.pdf"
            if rad_file.is_file():
                pdfs_a_unir.append(rad_file)

    if not pdfs_a_unir:
        return True, "\n".join(logs + ["No se encontraron archivos RAD.pdf para consolidar. Proceso omitido."])

    logs.append(f"Se encontraron {len(pdfs_a_unir)} archivos RAD.pdf para unir.")
    pdfs_a_unir.sort() # Ordenar alfabéticamente por ruta, lo que usualmente ordena por número de subcarpeta
    
    merger = PdfWriter()
    
    try:
        # 2. Leer y añadir cada PDF al objeto 'merger'
        for pdf_path in pdfs_a_unir:
            merger.append(str(pdf_path))
        
        # 3. Guardar el archivo unificado
        ruta_salida = carpeta_contenedora / nombre_salida
        with open(ruta_salida, "wb") as f_out:
            merger.write(f_out)
        
        logs.append(f"¡ÉXITO! Archivo consolidado guardado como '{ruta_salida.name}'.")
        merger.close()

        # 4. (Opcional pero recomendado) Limpiar los archivos RAD.pdf individuales
        for pdf_path in pdfs_a_unir:
            try:
                pdf_path.unlink()
            except OSError as e:
                logs.append(f"ADVERTENCIA: No se pudo eliminar el archivo individual {pdf_path.name}: {e}")
        logs.append("Archivos RAD.pdf individuales eliminados.")
        
        return True, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR CRÍTICO durante la consolidación de PDFs: {e}"
        traceback.print_exc()
        if 'merger' in locals(): merger.close()
        return False, "\n".join(logs + [error_msg])

def encontrar_documentos_facturacion_axa(subfolder_path: Path, nombre_subcarpeta: str) -> tuple[str | None, str | None, dict[str, Path] | None, str]:
    """
    Busca y valida los archivos requeridos para Facturación en AXA,
    incluyendo ahora el JSON (RIPS) y el XML (FEV).
    Devuelve: (codigo_factura, cuv, diccionario_archivos_a_subir, log)
    """
    subfolder_path = subfolder_path.resolve()
    log_prefix = f"[{nombre_subcarpeta}] "
    logs = [f"{log_prefix}Buscando archivos requeridos para AXA Facturación..."]
    
    encontrados = { "factura_pdf": None, "furips_pdf": None, "hc_pdf": None, "coex_json": None, "coex_xml": None, "resultados_json": None }
    codigo_factura, cuv = None, None
    pattern_codigo = re.compile(r"(COEX|FECR)(\d+)", re.IGNORECASE)

    try:
        # Búsqueda
        for item in subfolder_path.iterdir():
            if not item.is_file(): continue
            filename_upper = item.name.upper()

            # Identificar cada archivo
            if filename_upper.startswith("FACTURA_"): encontrados["factura_pdf"] = item
            elif filename_upper.startswith("FURIPS_"): encontrados["furips_pdf"] = item
            elif filename_upper.startswith("HC_"): encontrados["hc_pdf"] = item
            elif filename_upper.endswith(".XML"): encontrados["coex_xml"] = item
            elif "RESULTADOSMSPS" in filename_upper and "CUV" in filename_upper: encontrados["resultados_json"] = item
            elif ("COEX" in filename_upper or "FECR" in filename_upper) and filename_upper.endswith(".JSON"): encontrados["coex_json"] = item

            # Extraer código de factura
            if not codigo_factura:
                match = pattern_codigo.search(item.name)
                if match: codigo_factura = f"{match.group(1).upper()}{match.group(2)}"

        # Extracción del CUV
        if encontrados["resultados_json"]:
            try:
                with open(encontrados["resultados_json"], 'r', encoding='utf-8', errors='replace') as f:
                    data = json.load(f)
                    cuv = data.get("CodigoUnicoValidacion")
                if cuv: logs.append(f"{log_prefix}  -> CUV extraído.")
            except Exception as e_json: return None, None, None, f"{log_prefix}ERROR leyendo JSON de CUV: {e_json}"

        # Validación
        # Ahora RIPS (.json) y FEV (.xml) son también requeridos
        faltantes = [k for k in ["factura_pdf", "furips_pdf", "hc_pdf", "coex_json", "coex_xml", "resultados_json"] if not encontrados[k]]
        if faltantes: return None, None, None, f"{log_prefix}ERROR: Faltan archivos: {', '.join(faltantes)}"
        if not all([codigo_factura, cuv]): return None, None, None, f"{log_prefix}ERROR: No se pudo extraer el código de factura o el CUV."

        logs.append(f"{log_prefix}  -> Validación OK. Todos los archivos encontrados.")
        
        # <<< CAMBIO: Ahora devolvemos 5 archivos para subir >>>
        archivos_a_subir = {
            "factura": encontrados["factura_pdf"],
            "furips": encontrados["furips_pdf"],
            "hc": encontrados["hc_pdf"],
            "rips": encontrados["coex_json"],
            "fev": encontrados["coex_xml"]
        }
        
        return codigo_factura, cuv, archivos_a_subir, "\n".join(logs)

    except Exception as e:
        return None, None, None, f"{log_prefix}ERROR inesperado en 'encontrar_documentos': {e}"
    
def guardar_screenshot_de_error(page, nombre_base: str):
    """
    Toma una captura de pantalla de la página y la guarda en la carpeta
    temporal del sistema (%temp%) con un nombre de archivo único.

    Args:
        page: La instancia de la página de Playwright.
        nombre_base (str): Un nombre descriptivo para el archivo (ej: "login_previsora").
    """
    try:
        # Obtener la ruta a la carpeta temporal del sistema
        temp_dir = Path(tempfile.gettempdir())
        
        # Crear un nombre de archivo único para evitar sobreescribir
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"error_screenshot_{nombre_base}_{timestamp}.png"
        
        # Construir la ruta completa
        ruta_screenshot = temp_dir / filename
        
        # Tomar la captura de pantalla
        page.screenshot(path=ruta_screenshot)
        
        # Devolver la ruta donde se guardó para poder registrarla en el log
        return f"Screenshot de error guardado en: {ruta_screenshot}"
        
    except Exception as e:
        return f"FALLO AL GUARDAR SCREENSHOT: {e}"
    