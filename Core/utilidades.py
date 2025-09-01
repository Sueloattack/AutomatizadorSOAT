# AutomatizadorSOAT/nucleo/utilidades.py
from datetime import datetime
import os
import re
import sys
import traceback
from pathlib import Path
from email.header import decode_header


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
        # --- Búsqueda (sin cambios) ---
        for item in subfolder_path.iterdir():
            # ... (código de búsqueda como lo tenías) ...
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
def encontrar_documentos_facturacion(
    subfolder_path: Path, nombre_subcarpeta: str
) -> tuple[str | None, dict[str, Path] | None, str]:
    """
    Busca los documentos necesarios para un radicado de Facturación.

    Busca 4 archivos clave por su nombre (ignorando mayúsculas/minúsculas):
    1. FACTURA-[...].pdf
    2. RIPS-[...].pdf
    3. SOPORTES-[...].pdf
    4. ANEXOS-[...].pdf

    Extrae el código de la factura del nombre del archivo de factura.

    Devuelve:
    - El código de la factura a usar en el formulario.
    - Un diccionario con las rutas a los archivos encontrados.
    - Un log del proceso.
    """
    subfolder_path = subfolder_path.resolve()
    log_prefix = f"[{nombre_subcarpeta}] "
    log_messages = [f"{log_prefix}Buscando documentos de Facturación..."]

    documentos_encontrados = {}
    codigo_factura = None

    # Patrón para extraer el código del archivo de factura.
    # Ej: "FACTURA-FECR12345.pdf" -> captura "FECR12345"
    factura_pattern = re.compile(r"FACTURA-([A-Z0-9]+)\.pdf", re.IGNORECASE)

    try:
        if not subfolder_path.is_dir():
            return None, None, f"{log_prefix}ERROR: Subcarpeta no existe."

        for item in subfolder_path.iterdir():
            if not item.is_file():
                continue
            
            filename_lower = item.name.lower()
            
            if filename_lower.startswith("factura-"):
                documentos_encontrados["factura"] = item
                match = factura_pattern.match(item.name)
                if match:
                    codigo_factura = match.group(1).upper()
                    log_messages.append(f"{log_prefix}  -> Encontrada FACTURA: {item.name} (Código: {codigo_factura})")

            elif filename_lower.startswith("rips-"):
                documentos_encontrados["rips"] = item
                log_messages.append(f"{log_prefix}  -> Encontrados RIPS: {item.name}")
                
            elif filename_lower.startswith("soportes-"):
                documentos_encontrados["soportes"] = item
                log_messages.append(f"{log_prefix}  -> Encontrados SOPORTES: {item.name}")

            elif filename_lower.startswith("anexos-"):
                documentos_encontrados["anexos"] = item
                log_messages.append(f"{log_prefix}  -> Encontrados ANEXOS: {item.name}")
        
        # Validación
        documentos_requeridos = ["factura", "rips", "soportes", "anexos"]
        faltantes = [doc for doc in documentos_requeridos if doc not in documentos_encontrados]

        if faltantes:
            error_msg = f"{log_prefix}ERROR: Faltan documentos requeridos: {', '.join(faltantes)}"
            return None, None, "\n".join(log_messages + [error_msg])
        
        if not codigo_factura:
            return None, None, f"{log_prefix}ERROR: Se encontró el PDF de factura, pero no se pudo extraer el código."
            
        log_messages.append(f"{log_prefix}Todos los documentos de facturación requeridos fueron encontrados.")
        return codigo_factura, documentos_encontrados, "\n".join(log_messages)

    except Exception as e:
        error_msg = f"{log_prefix}Error inesperado buscando documentos de facturación: {e}"
        traceback.print_exc()
        return None, None, "\n".join(log_messages + [error_msg])
    
