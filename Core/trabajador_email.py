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

    def _search_single_email(self, radicado_number, folder_path):
        """Busca un único email usando la conexión persistente."""
        try:
            # Seleccionar INBOX en cada búsqueda refresca la vista del servidor
            self.imap.select("INBOX")
            
            # --- BÚSQUEDA REAL Y COMPLETA ---
            status, messages = self.imap.search(None, 'ALL')
            if status != "OK" or not messages[0]: return False

            all_ids = messages[0].split(); latest_ids = all_ids[-50:]

            for email_id in reversed(latest_ids):
                # 1. Obtener solo la cabecera para ser rápido
                _, header_data = self.imap.fetch(email_id, '(BODY[HEADER.FIELDS (FROM DATE)])')
                header_msg = email.message_from_bytes(header_data[0][1])

                # 2. Filtrar por fecha y remitente en Python
                email_date = parsedate_to_datetime(header_msg['Date'])
                if email_date.date() != datetime.now().date(): continue
                from_header = str(decode_header(header_msg['From'])[0][0])
                if AXASOAT_EMAIL_SENDER not in from_header: continue
                
                # 3. Si coincide, obtener el cuerpo completo
                _, full_msg_data = self.imap.fetch(email_id, '(RFC822)')
                full_msg = email.message_from_bytes(full_msg_data[0][1])

                for part in full_msg.walk():
                    if part.get_filename():
                        filename = part.get_filename()
                        if radicado_number in filename and filename.lower().endswith(".pdf"):
                            self.progreso_update.emit(f"  -> ¡COINCIDENCIA! Adjunto: {filename}")
                            ruta_guardado = folder_path / filename
                            with open(ruta_guardado, "wb") as f: f.write(part.get_payload(decode=True))
                            
                            self.progreso_update.emit("  -> Moviendo correo procesado...")
                            self.imap.copy(email_id, EMAIL_PROCESSED_FOLDER)
                            self.imap.store(email_id, '+FLAGS', '\\Deleted')
                            self.imap.expunge()
                            return True
            return False # No se encontró en este ciclo
        except Exception as e:
            self.progreso_update.emit(f"  -> ERROR en búsqueda para {radicado_number}: {e}")
            # Si hay un error, reconectamos en la siguiente iteración por seguridad
            if self.imap: self.imap.logout()
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