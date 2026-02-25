# Core/trabajador_email.py

from PySide6 import QtCore
import queue
import traceback
import time
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime
from pathlib import Path
import locale

# Importamos las constantes necesarias
from Configuracion.constantes import (
    EMAIL_IMAP_SERVER, EMAIL_USER_ADDRESS, EMAIL_APP_PASSWORD,
    AXASOAT_EMAIL_SENDER, EMAIL_SEARCH_RETRIES, EMAIL_SEARCH_DELAY_SECONDS,
    EMAIL_PROCESSED_FOLDER
)

class EmailListenerWorker(QtCore.QObject):
    progreso_update = QtCore.Signal(str)
    finished = QtCore.Signal(list)

    def __init__(self, job_queue: queue.Queue):
        super().__init__()
        self.job_queue = job_queue
        self.is_running = True
        self.failed_jobs = []
        self.imap = None

    def _connect(self):
        try:
            self.progreso_update.emit("[EMAIL_LISTENER] Estableciendo conexión IMAP...")
            self.imap = imaplib.IMAP4_SSL(EMAIL_IMAP_SERVER)
            self.imap.login(EMAIL_USER_ADDRESS, EMAIL_APP_PASSWORD)
            self.progreso_update.emit("[EMAIL_LISTENER] Conexión establecida con éxito.")
            return True
        except Exception as e:
            self.progreso_update.emit(f"[EMAIL_LISTENER] ERROR CRÍTICO al conectar a IMAP: {e}")
            self.is_running = False
            return False

    def _decode_header_value(self, value):
        """Decodifica cabeceras que pueden venir en formatos como =?utf-8?B?...?="""
        if not value: return ""
        try:
            decoded_parts = decode_header(value)
            result = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    result += part.decode(encoding if encoding else 'utf-8', errors='replace')
                else:
                    result += str(part)
            return result
        except Exception:
            return str(value)

    def _search_single_email(self, radicado_number, folder_path):
        """Busca un único email usando la conexión persistente con lógica mejorada."""
        try:
            # Seleccionar INBOX en cada búsqueda refresca la vista del servidor
            self.imap.select("INBOX")
            
            # --- MEJORA 1: Búsqueda Filtrada en el Servidor (Optimización) ---
            # Buscamos desde ayer para cubrir cambios de fecha o retrasos.
            from datetime import timedelta
            yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")
            
            # Criterio de búsqueda: remitente, fecha (desde ayer) y texto específico (radicado)
            # El criterio TEXT busca en el cuerpo y asunto, lo que es muy potente.
            search_query = f'(FROM "{AXASOAT_EMAIL_SENDER}" SINCE {yesterday_str} TEXT "{radicado_number}")'
            status, messages = self.imap.search(None, search_query)
            
            if status != "OK" or not messages[0]:
                self.progreso_update.emit(f"  [EMAIL] No se encontraron correos con el radicado {radicado_number} desde el {yesterday_str}")
                return False

            all_ids = messages[0].split()
            # Como ya filtramos por radicado, es poco probable tener cientos de correos.
            # Aun así, tomamos los últimos por si hubiera reintentos de AXA.
            latest_ids = all_ids[-20:]

            for email_id in reversed(latest_ids):
                # 1. Obtener cabeceras (From, Date, Subject) para pre-filtrado rápido
                _, header_data = self.imap.fetch(email_id, '(BODY[HEADER.FIELDS (FROM DATE SUBJECT)])')
                if not header_data or not header_data[0]: continue
                header_msg = email.message_from_bytes(header_data[0][1])

                # 2. Decodificar remitente y asunto
                from_header = self._decode_header_value(header_msg['From'])
                subject = self._decode_header_value(header_msg['Subject'])
                
                # Re-validar remitente por si el SEARCH de IMAP fue muy permisivo
                if AXASOAT_EMAIL_SENDER not in from_header: continue
                
                self.progreso_update.emit(f"  [EMAIL] Revisando: '{subject}' (ID: {email_id.decode()})")

                # 3. Obtener el cuerpo completo solo si pasó el filtro inicial
                _, full_msg_data = self.imap.fetch(email_id, '(RFC822)')
                if not full_msg_data or not full_msg_data[0]: continue
                full_msg = email.message_from_bytes(full_msg_data[0][1])

                found_attachment = False
                for part in full_msg.walk():
                    # Ignorar partes que no son adjuntos
                    if part.get_content_maintype() == 'multipart': continue
                    if part.get('Content-Disposition') is None: continue

                    filename = self._decode_header_value(part.get_filename())
                    if not filename: continue

                    # --- MEJORA 2: Coincidencia más flexible ---
                    # Buscamos el radicado en el nombre del archivo o en el asunto como respaldo
                    if (radicado_number in filename or radicado_number in subject) and filename.lower().endswith(".pdf"):
                        self.progreso_update.emit(f"  -> ¡COINCIDENCIA ENCONTRADA! Adjunto: {filename}")
                        ruta_guardado = folder_path / filename
                        
                        # Guardar el archivo
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                with open(ruta_guardado, "wb") as f:
                                    f.write(payload)
                                found_attachment = True
                                break
                        except Exception as e_save:
                            self.progreso_update.emit(f"  -> ERROR guardando adjunto {filename}: {e_save}")

                if found_attachment:
                    # Mover el correo a la carpeta de procesados para no volverlo a leer
                    self.progreso_update.emit("  -> Moviendo correo procesado...")
                    try:
                        self.imap.copy(email_id, EMAIL_PROCESSED_FOLDER)
                        self.imap.store(email_id, '+FLAGS', '\\Deleted')
                        self.imap.expunge()
                    except Exception as e_move:
                        self.progreso_update.emit(f"  -> AVISO: No se pudo mover/borrar el correo (ID {email_id}): {e_move}")
                    return True

            return False # No se encontró en este ciclo
        except Exception as e:
            self.progreso_update.emit(f"  -> ERROR en búsqueda para {radicado_number}: {e}")
            # Si hay un error de conexión, intentamos reconectar
            try: 
                if self.imap: self.imap.logout()
            except: pass
            self._connect()
            return False

    @QtCore.Slot()
    def run(self):
        self.progreso_update.emit("--- Hilo de Escucha de Email INICIADO (Modo Conexión Persistente) ---")
        if not self._connect(): return

        # --- LÓGICA DE "KEEP-ALIVE" (MANTENER LA CONEXIÓN VIVA) ---
        last_noop_time = time.time()
        NOOP_INTERVAL_SECONDS = 240 # Enviar un NOOP cada 4 minutos (240 segundos)
        
        # --- PRIMERA PASADA ---
        while self.is_running:
            try:
                job = self.job_queue.get(timeout=1)
                if job is None: self.is_running = False; continue
                radicado, folder_path = job
                
                # Bucle de reintentos para un solo radicado
                found = False
                for i in range(EMAIL_SEARCH_RETRIES):
                    self.progreso_update.emit(f"[EMAIL_LISTENER] Buscando {radicado} (Intento {i+1})...")
                    if self._search_single_email(radicado, folder_path):
                        found = True
                        break
                    time.sleep(EMAIL_SEARCH_DELAY_SECONDS)

                if not found:
                    self.progreso_update.emit(f"[EMAIL_LISTENER] ADVERTENCIA: No se encontró {radicado} en 1ª pasada. Se repasará.")
                    self.failed_jobs.append(job)

            except queue.Empty:
                # --- La cola está vacía, aquí es donde manejamos la inactividad ---
                current_time = time.time()
                if current_time - last_noop_time > NOOP_INTERVAL_SECONDS:
                    try:
                        self.progreso_update.emit("[EMAIL_LISTENER] Conexión inactiva, enviando NOOP para mantenerla viva...")
                        self.imap.noop()
                        self.progreso_update.emit("[EMAIL_LISTENER] NOOP exitoso. La conexión está activa.")
                        last_noop_time = current_time
                    except (imaplib.IMAP4.abort, imaplib.IMAP4.readonly) as e:
                        # Si el NOOP falla, significa que la conexión ya se había perdido.
                        self.progreso_update.emit(f"[EMAIL_LISTENER] ADVERTENCIA: La conexión se perdió ({e}). Intentando reconectar...")
                        self._connect() # Intentar restablecer la conexión para el siguiente ciclo.
                        last_noop_time = time.time()
                continue
        
        # --- CICLO DE REPASO ---
        for i in range(3): # Repasar la lista de fallos 3 veces
            if not self.failed_jobs: break
            self.progreso_update.emit(f"\n--- REPASO FINAL #{i+1}: {len(self.failed_jobs)} pendiente(s) ---")
            time.sleep(30)
            
            still_failed = []
            for job in self.failed_jobs:
                radicado, folder_path = job
                if not self._search_single_email(radicado, folder_path):
                    still_failed.append(job)
            self.failed_jobs = still_failed
        
        self.progreso_update.emit("[EMAIL_LISTENER] Desconectando de IMAP...")
        if self.imap: self.imap.logout()
        self.progreso_update.emit("[EMAIL_LISTENER] Desconectado de IMAP...")
        self.finished.emit(self.failed_jobs)