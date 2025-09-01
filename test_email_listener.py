# test_email_listener.py

import imaplib
import email
import time
from email.header import decode_header
from datetime import datetime
import locale
import traceback

# --- CONFIGURACIÓN (COPIA ESTO DE TU archivo constantes.py) ---
EMAIL_IMAP_SERVER = "imap.gmail.com"
EMAIL_USER_ADDRESS = "radicacionglosa@asotrauma.com.co"
EMAIL_APP_PASSWORD = "yuzy hkzu rnsi vggx"


TARGET_SENDER = "notificaciones@claimonline.com.co"
TARGET_FOLDER = "Procesados" 
RADICADO_A_BUSCAR = "22374196" # <-- Cambia esto por un radicado real que SEPAS que está en tu correo
# ------------------------------------------------------------------

def decode_header_str(header):
    """Función de ayuda para decodificar cabeceras de email."""
    decoded_parts = decode_header(header)
    final_str = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            final_str.append(part.decode(encoding or 'utf-8', errors='ignore'))
        else:
            final_str.append(part)
    return "".join(final_str)

def main():
    print("--- INICIANDO SCRIPT DE DIAGNÓSTICO IMAP (ENFOCADO) ---")
    print(f"Buscando en la carpeta: '{TARGET_FOLDER}'")
    print(f"Correos del remitente: '{TARGET_SENDER}'")
    print(f"Buscando el radicado: '{RADICADO_A_BUSCAR}'")

    imap = None  # Inicializar fuera del try
    try:
        imap = imaplib.IMAP4_SSL(EMAIL_IMAP_SERVER)
        imap.login(EMAIL_USER_ADDRESS, EMAIL_APP_PASSWORD)
        print("\n[SUCCESS] Conexión y login exitosos.")
        
        # --- Seleccionar la carpeta/etiqueta 'Procesados' ---
        status, _ = imap.select(f'"{TARGET_FOLDER}"') # Las etiquetas de Gmail a veces necesitan comillas
        if status != "OK":
            print(f"\n[ERROR] No se pudo seleccionar la carpeta '{TARGET_FOLDER}'. ¿Existe?")
            return

        print(f"[INFO] Carpeta '{TARGET_FOLDER}' seleccionada con éxito.")
        
        # --- Usar el filtro directo del servidor ---
        search_criteria = f'(FROM "{TARGET_SENDER}")'
        print(f"[INFO] Ejecutando búsqueda con el criterio: {search_criteria}")
        status, messages = imap.search(None, search_criteria)
        
        if status != "OK" or not messages[0]:
            print("\n[RESULTADO] La búsqueda del servidor NO devolvió ningún correo de ese remitente en esta carpeta.")
            return

        email_ids = messages[0].split()
        print(f"\n[RESULTADO] ¡Éxito! El servidor encontró {len(email_ids)} correo(s) de '{TARGET_SENDER}'.")
        print("--- Analizando el contenido de cada correo encontrado ---")

        radicado_encontrado = False
        for email_id in email_ids:
            # Descargar el cuerpo completo de cada correo encontrado
            _, msg_data = imap.fetch(email_id, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            from_addr = decode_header_str(msg['From'])
            subject = decode_header_str(msg['Subject'])
            
            print(f"\n  - Revisando Email ID: {email_id.decode()}")
            print(f"    De: {from_addr}")
            print(f"    Asunto: {subject}")

            # Buscar el adjunto
            for part in msg.walk():
                if part.get_filename():
                    filename = part.get_filename()
                    print(f"    [ADJUNTO] Encontrado archivo: {filename}")
                    if RADICADO_A_BUSCAR in filename:
                        print(f"      [¡¡¡MATCH!!!] Se encontró el radicado '{RADICADO_A_BUSCAR}' en este adjunto.")
                        radicado_encontrado = True

        if not radicado_encontrado:
            print(f"\n[INFO] Se encontraron correos del remitente, pero ninguno contenía el radicado '{RADICADO_A_BUSCAR}' en su adjunto.")

    except Exception as e:
        print(f"\n[ERROR] Ocurrió un error inesperado: {e}")
        traceback.print_exc()
    finally:
        if imap:
            print("\n[INFO] Cerrando conexión IMAP.")
            try:
                imap.close()
                imap.logout()
            except:
                pass

if __name__ == "__main__":
    main()