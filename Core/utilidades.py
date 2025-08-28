# AutomatizadorSOAT/nucleo/utilidades.py
import os
import re
import sys
import traceback
from pathlib import Path
import imaplib
import email
from email.header import decode_header
import time

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

def encontrar_y_validar_pdfs(
    subfolder_path: Path, nombre_subcarpeta: str, nombre_aseguradora_en_pdf: str
) -> tuple[str | None, Path | None, str]:
    """
    Busca y valida los PDFs de Glosa (Respuesta y Carta) de forma universal e inteligente.

    Funcionalidades:
    1.  Universal: Acepta el nombre de la aseguradora para buscarlo dinámicamente en el PDF de la carta.
    2.  Inteligente: Si el nombre de la subcarpeta contiene "sin carta glosa", puede proceder
        utilizando únicamente el PDF de respuesta glosa, si este existe.

    Devuelve el código final de la factura, la ruta al PDF de respuesta para cargar y un log detallado.
    """
    subfolder_path = subfolder_path.resolve()
    log_prefix = f"[{nombre_subcarpeta}] "
    log_messages = [f"{log_prefix}Validando PDFs (Lógica Centralizada)..."]

    # --- Manejo inteligente de "sin carta glosa" ---
    ignorar_carta_faltante = "sin carta glosa" in nombre_subcarpeta.lower()
    if ignorar_carta_faltante:
        log_messages.append(f"{log_prefix}  -> DETECTADO: 'sin carta glosa'. Se procederá solo con la respuesta si se encuentra.")

    # --- Definición de Patrones ---
    # Patrón para la RESPUESTA DE GLOSA (es estándar)
    respuesta_glosa_pattern = re.compile(r"^(FECR|COEX|FERD|FERR|FCR)(\d+)\.pdf$", re.IGNORECASE)

    # Patrón dinámico para la CARTA DE GLOSA
    # Se escapa el nombre de la aseguradora para manejar caracteres especiales como '.'
    nombre_escapado = re.escape(nombre_aseguradora_en_pdf)
    carta_glosa_pattern = re.compile(
        rf".*?([A-Z]+)[_-](\d+)[_-]{nombre_escapado}.*?\.pdf$", re.IGNORECASE
    )

    respuesta_glosa_info = None
    candidatos_carta_glosa = []

    try:
        if not subfolder_path.is_dir():
            return None, None, f"{log_prefix}ERROR: Subcarpeta no existe."

        # --- Búsqueda de Archivos en la Subcarpeta ---
        for item in subfolder_path.iterdir():
            if not item.is_file():
                continue
            
            filename = item.name
            if filename.upper() == "RAD.PDF":
                continue

            # Buscar la Respuesta de Glosa (la primera que encuentre)
            if not respuesta_glosa_info:
                match_respuesta = respuesta_glosa_pattern.match(filename)
                if match_respuesta:
                    codigo_respuesta = f"{match_respuesta.group(1).upper()}{match_respuesta.group(2)}"
                    respuesta_glosa_info = {
                        "path": item,
                        "filename": filename,
                        "codigo": codigo_respuesta
                    }
                    log_messages.append(f"{log_prefix}  -> Encontrada Respuesta Glosa: '{filename}' (Código: {codigo_respuesta})")

            # Buscar la Carta de Glosa
            match_carta = carta_glosa_pattern.match(filename)
            if match_carta:
                prefijo_carta = match_carta.group(1).upper()
                numero_carta = match_carta.group(2)
                codigo_limpio_carta = f"{prefijo_carta}{numero_carta}"
                candidatos_carta_glosa.append({
                    "path": item,
                    "filename": filename,
                    "codigo_limpio": codigo_limpio_carta
                })
                log_messages.append(f"{log_prefix}  -> Encontrado candidato a Carta Glosa: '{filename}' (Código limpio: {codigo_limpio_carta})")

        # --- Validación de Resultados ---
        if not respuesta_glosa_info:
            return None, None, f"{log_prefix}ERROR: No se encontró el archivo de Respuesta de Glosa (ej: FERR123.pdf)."
        
        # Si NO encontramos la carta Y NO tenemos permiso explícito para ignorarla, es un error.
        if not candidatos_carta_glosa and not ignorar_carta_faltante:
            return None, None, f"{log_prefix}ERROR: No se encontró el archivo de Carta de Glosa (ej: ..._{nombre_aseguradora_en_pdf}.pdf)."

        # --- Determinación del Código de Factura Final ---
        if candidatos_carta_glosa:
            # Lógica estándar: el código de la carta es la fuente de verdad.
            carta_glosa_seleccionada = candidatos_carta_glosa[0] # Tomamos el primero
            codigo_final_factura = carta_glosa_seleccionada["codigo_limpio"]
            log_messages.append(f"{log_prefix}Código final se tomará de la Carta: '{codigo_final_factura}'")
        else:
            # Caso especial "sin carta glosa": usamos el código de la respuesta.
            codigo_final_factura = respuesta_glosa_info["codigo"]
            log_messages.append(f"{log_prefix}No hay Carta (permitido por nombre de carpeta). Código final se tomará de la Respuesta: '{codigo_final_factura}'")

        path_respuesta_a_cargar = respuesta_glosa_info["path"]
        codigo_respuesta = respuesta_glosa_info["codigo"]

        if codigo_respuesta != codigo_final_factura:
            log_messages.append(f"{log_prefix}ADVERTENCIA: Discrepancia de códigos detectada (Respuesta: '{codigo_respuesta}', Final: '{codigo_final_factura}'). Se usará el código final.")
            # Aquí podrías añadir la lógica de renombrado si es necesario para Axa.
            # Por ahora, solo advertimos y continuamos.
        else:
            log_messages.append(f"{log_prefix}Códigos de Respuesta y Carta coinciden. Validación OK.")
        
        return codigo_final_factura, path_respuesta_a_cargar, "\n".join(log_messages)

    except Exception as e:
        error_msg = f"{log_prefix}Error inesperado procesando PDFs: {e}"
        traceback.print_exc()
        return None, None, "\n".join(log_messages + [error_msg])
    
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
    
def buscar_y_guardar_radicado_email(radicado_number: str, output_folder: Path) -> tuple[bool, str]:
    """
    Se conecta al email, obtiene TODOS los correos recientes/no leídos, y los filtra
    en Python para encontrar el del remitente correcto con el adjunto que coincide.
    Luego lo descarga y MUEVE el correo a la carpeta de procesados.
    """
    logs = [f"  Buscando email de confirmación para radicado: {radicado_number}..."]
    try:
        imap = imaplib.IMAP4_SSL(EMAIL_IMAP_SERVER)
        imap.login(EMAIL_USER_ADDRESS, EMAIL_APP_PASSWORD)
        logs.append(f"  -> Conectado a {EMAIL_IMAP_SERVER}.")
        imap.select("INBOX")
        
        email_encontrado = False
        id_correo_procesado = None

        for i in range(EMAIL_SEARCH_RETRIES):
            email_ids = []
            
            # --- NUEVA ESTRATEGIA DE BÚSQUEDA ---
            logs.append(f"  -> Intento {i+1}/{EMAIL_SEARCH_RETRIES}: Buscando correos...")
            
            # 1. Primero, intentar buscar por NO LEÍDOS (UNSEEN). Es el método más eficiente.
            status_unseen, messages_unseen = imap.search(None, '(UNSEEN)')
            if status_unseen == "OK" and messages_unseen[0]:
                email_ids = messages_unseen[0].split()
                logs.append(f"  -> {len(email_ids)} correo(s) NO LEÍDO(S) encontrado(s).")
            else:
                # 2. Si no hay no leídos, buscar TODOS los correos y tomar los 30 más recientes.
                #    Esto resuelve el problema de que otro cliente de email marque el correo como leído.
                logs.append("  -> No se encontraron correos no leídos. Buscando en los más recientes...")
                status_all, messages_all = imap.search(None, 'ALL')
                if status_all == "OK" and messages_all[0]:
                    # Tomamos solo los últimos 30 IDs para no procesar toda la bandeja de entrada
                    all_ids = messages_all[0].split()
                    email_ids = all_ids[-30:] 
                    logs.append(f"  -> Analizando los {len(email_ids)} correos más recientes.")

            if not email_ids:
                logs.append(f"  -> No se encontraron correos nuevos. Esperando {EMAIL_SEARCH_DELAY_SECONDS}s...")
                time.sleep(EMAIL_SEARCH_DELAY_SECONDS)
                continue

            # 3. FILTRADO EN PYTHON: Iterar sobre los IDs y verificar el remitente manualmente.
            for email_id in reversed(email_ids): # Empezar por el más reciente
                _, msg_data = imap.fetch(email_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                # Decodificar el header 'From' para obtener la dirección
                from_header = decode_header(msg['From'])[0][0]
                if isinstance(from_header, bytes):
                    from_header = from_header.decode()
                
                # ¡Aquí está el filtro que antes fallaba en el servidor!
                if AXASOAT_EMAIL_SENDER not in from_header:
                    continue # Si no es del remitente, saltar al siguiente correo.
                
                logs.append(f"  -> Correo de '{AXASOAT_EMAIL_SENDER}' encontrado. Analizando adjuntos...")

                # El resto de la lógica es la misma: buscar el adjunto correcto
                for part in msg.walk():
                    if part.get_content_maintype() == 'application' and part.get_filename():
                        filename = part.get_filename()
                        if radicado_number in filename and filename.lower().endswith(".pdf"):
                            logs.append(f"  -> ¡COINCIDENCIA ENCONTRADA! Adjunto: {filename}")
                            ruta_guardado = output_folder / filename
                            with open(ruta_guardado, "wb") as f: f.write(part.get_payload(decode=True))
                            logs.append(f"  -> Adjunto descargado y guardado como: {ruta_guardado.name}")
                            email_encontrado = True
                            id_correo_procesado = email_id
                            break # Salir del bucle de partes
                if email_encontrado: break # Salir del bucle de correos
            
            if email_encontrado: break # Salir del bucle de reintentos

        # Post-procesamiento (mover el correo) no cambia
        if id_correo_procesado:
            logs.append(f"  -> Moviendo correo a la carpeta '{EMAIL_PROCESSED_FOLDER}'...")
            imap.copy(id_correo_procesado, EMAIL_PROCESSED_FOLDER)
            imap.store(id_correo_procesado, '+FLAGS', '\\Deleted')
            imap.expunge()
            logs.append("  -> Correo movido con éxito.")

        imap.close()
        imap.logout()
        
        if not email_encontrado:
            return False, "\n".join(logs + ["  -> ERROR: Tiempo de espera agotado. No se encontró el adjunto correcto."])
            
        return True, "\n".join(logs)
        
    except Exception as e:
        error_msg = f"  -> ERROR CRÍTICO en el módulo de email: {e}"; traceback.print_exc()
        return False, "\n".join(logs + [error_msg])