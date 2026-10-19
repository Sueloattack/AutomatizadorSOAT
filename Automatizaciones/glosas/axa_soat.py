# AutomatizadorSOAT/Automatizaciones/glosas/axa_soat.py

import re
import time
import traceback
import imaplib
import email
from pathlib import Path
from datetime import datetime # Necesario para la fecha de hoy
from PIL import Image
from playwright.sync_api import Page, expect, TimeoutError as PlaywrightTimeoutError

try:
    from Configuracion.constantes import *
    from Core.utilidades import encontrar_y_validar_pdfs, guardar_screenshot_de_error
except ImportError as e:
    raise ImportError(f"ERROR CRITICO: No se pudieron importar constantes: {e}")

# Estados consistentes con otros módulos
ESTADO_EXITO = "EXITO"
ESTADO_FALLO = "FALLO"
ESTADO_OMITIDO_RADICADO = "OMITIDO_RADICADO"
ESTADO_OMITIDO_DUPLICADA = "OMITIDO_DUPLICADA"

def check_server_error(page: Page) -> bool:
    """Verifica si la página actual muestra un error de servidor '502 Bad Gateway'."""
    try:
        # is_visible() no espera el timeout completo si lo encuentra, es rápido.
        # Le damos un timeout muy corto. Si no lo encuentra, no es un error, significa que la página está OK.
        if page.locator(AXASOAT_SELECTOR_SERVER_ERROR_H1).is_visible(timeout=1000):
            return True
    except PlaywrightTimeoutError:
        # Esto es lo esperado si el elemento no existe (la página está bien).
        pass
    return False


def get_initial_email_ids() -> set:
    """Obtiene el conjunto de IDs de correos existentes de notificaciones@claimonline.com.co."""
    for _ in range(3):
        try:
            imap = imaplib.IMAP4_SSL(EMAIL_IMAP_SERVER, timeout=15)
            imap.login(EMAIL_USER_ADDRESS, EMAIL_APP_PASSWORD)
            imap.select("INBOX", readonly=True)
            _, messages = imap.search(None, f'(FROM "{AXASOAT_EMAIL_SENDER}")')
            ids = set(messages[0].split()) if messages[0] else set()
            imap.logout()
            return ids
        except Exception:
            time.sleep(1)
    return set()

def wait_for_otp_code(initial_ids: set, timeout: int = 120, allow_recent_fallback: bool = True) -> str | None:
    """Espera la llegada de un nuevo correo o toma el código reciente emitido por ClaimOnline."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            imap = imaplib.IMAP4_SSL(EMAIL_IMAP_SERVER, timeout=15)
            imap.login(EMAIL_USER_ADDRESS, EMAIL_APP_PASSWORD)
            imap.select("INBOX", readonly=True)
            _, messages = imap.search(None, f'(FROM "{AXASOAT_EMAIL_SENDER}")')
            if messages[0]:
                current_ids = messages[0].split()
                new_ids = [mid for mid in current_ids if mid not in initial_ids]
                target_id = None
                
                if new_ids:
                    target_id = new_ids[-1]
                elif allow_recent_fallback and (time.time() - start > 10):
                    # Si no ha entrado un ID nuevo pero existe un correo de hace menos de 10 minutos
                    last_id = current_ids[-1]
                    _, d_hdr = imap.fetch(last_id, '(BODY.PEEK[HEADER.FIELDS (DATE)])')
                    hdr_txt = d_hdr[0][1].decode('utf-8', errors='ignore')
                    m_date = re.search(r"Date:\s*(.+)", hdr_txt, re.IGNORECASE)
                    if m_date:
                        date_tuple = email.utils.parsedate_tz(m_date.group(1).strip())
                        if date_tuple:
                            from datetime import timezone
                            msg_dt = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple), timezone.utc)
                            now_dt = datetime.now(timezone.utc)
                            if (now_dt - msg_dt).total_seconds() < 1800: # Menos de 30 minutos
                                target_id = last_id

                if target_id:
                    _, data = imap.fetch(target_id, "(RFC822)")
                    msg = email.message_from_bytes(data[0][1])
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            h = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            m = re.search(r"<span><b>(\d{6})</b></span>", h) or re.search(r"<b>\s*(\d{6})\s*</b>", h)
                            if m:
                                code = m.group(1)
                                imap.logout()
                                return code
            imap.logout()
        except Exception:
            pass
        time.sleep(3)
    return None

def descargar_soporte_radicado_correo(radicado_number: str, folder_path: Path, timeout: int = 40) -> tuple[bool, str]:
    """
    Busca en el correo el mensaje de confirmación de AXA ClaimOnline para el radicado especificado
    y descarga el PDF oficial adjunto (con el sello, fechas legales y firma).
    """
    logs = [f"  [CORREO] Buscando soporte oficial de radicación para el radicado {radicado_number}..."]
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            imap = imaplib.IMAP4_SSL(EMAIL_IMAP_SERVER, timeout=15)
            imap.login(EMAIL_USER_ADDRESS, EMAIL_APP_PASSWORD)
            imap.select("INBOX", readonly=True)
            
            # Buscar correos de AXA que contengan el número de radicado en TEXT o SUBJECT
            status, messages = imap.search(None, f'(FROM "{AXASOAT_EMAIL_SENDER}" TEXT "{radicado_number}")')
            if status != "OK" or not messages[0]:
                status, messages = imap.search(None, f'(FROM "{AXASOAT_EMAIL_SENDER}")')

            if status == "OK" and messages[0]:
                msg_ids = messages[0].split()
                # Revisar los más recientes primero
                for msg_id in reversed(msg_ids[-10:]):
                    _, data = imap.fetch(msg_id, "(RFC822)")
                    if not data or not data[0]:
                        continue
                    msg = email.message_from_bytes(data[0][1])
                    
                    # Revisar adjuntos
                    for part in msg.walk():
                        if part.get_content_maintype() == 'multipart':
                            continue
                        if part.get('Content-Disposition') is None:
                            continue
                        
                        fn = part.get_filename() or ""
                        if radicado_number in fn and fn.lower().endswith(".pdf"):
                            payload = part.get_payload(decode=True)
                            if payload:
                                target_pdf = folder_path / fn
                                with open(target_pdf, "wb") as f:
                                    f.write(payload)
                                imap.logout()
                                logs.append(f"  -> ¡Soporte oficial del correo descargado con ÉXITO!: '{fn}'")
                                return True, "\n".join(logs)
            imap.logout()
        except Exception as e:
            logs.append(f"  -> Aviso en búsqueda de correo: {e}")
        
        time.sleep(4)
        
    logs.append(f"  -> Aviso: No llegó a tiempo el correo con adjunto para {radicado_number}. Se mantiene la captura del modal.")
    return False, "\n".join(logs)

def login(page: Page) -> tuple[bool, str]:
    """Realiza el login en AXA SOAT (ClaimOnline), gestiona 2FA/OTP por correo y navega a Recepción."""
    logs = ["Iniciando login en AXA SOAT (ClaimOnline)..."]
    try:
        page.goto(AXASOAT_LOGIN_URL, timeout=60000)
        logs.append(f"  Página cargada: {AXASOAT_LOGIN_URL}")

        # Verificación de página caída
        if check_server_error(page):
            error_msg = "ERROR CRÍTICO: El servidor de AXA parece estar caído (Error 502)."
            logs.append(error_msg)
            return False, "\n".join(logs)

        # 2. Llenar los datos de acceso
        # Rellenar visualmente con Playwright
        page.locator("input[placeholder='Ingresar correo']").fill(AXASOAT_CORREO_LOGIN)
        page.locator("select").select_option(value=AXASOAT_TIPO_RECLAMANTE_VAL)
        page.locator("input[placeholder*='documento']").fill(AXASOAT_DOCUMENTO_LOGIN)

        # Sincronizar el estado interno de React Fiber en LoginPageReception
        page.evaluate(f"""() => {{
            const root = document.querySelector('#root');
            const rKey = Object.keys(root).find(k => k.startsWith('__reactContainer') || k.startsWith('__reactFiber'));
            let node = root[rKey];
            let found = null;
            function walk(n) {{
                if (!n || found) return;
                if (n.type && typeof n.type === 'function' && n.type.name === 'LoginPageReception') {{
                    found = n;
                    return;
                }}
                walk(n.child);
                walk(n.sibling);
            }}
            walk(node);
            if (found) {{
                let hook = found.memoizedState;
                let idx = 0;
                let setDataLogin = null, setEmailValid = null, setDniValid = null, setBtnDisabled = null;
                while (hook) {{
                    if (idx === 4) setDataLogin = hook.queue.dispatch;
                    if (idx === 11) setEmailValid = hook.queue.dispatch;
                    if (idx === 15) setDniValid = hook.queue.dispatch;
                    if (idx === 18) setBtnDisabled = hook.queue.dispatch;
                    hook = hook.next;
                    idx++;
                }}
                if (setDataLogin) {{
                    setDataLogin({{
                        tokenCaptcha: '',
                        ip: null,
                        email: '{AXASOAT_CORREO_LOGIN}',
                        claimantTypeId: '{AXASOAT_TIPO_RECLAMANTE_VAL}',
                        dni: '{AXASOAT_DOCUMENTO_LOGIN}'
                    }});
                }}
                if (setEmailValid) setEmailValid(true);
                if (setDniValid) setDniValid(false);
                if (setBtnDisabled) setBtnDisabled(false);
            }}
        }}""")

        logs.append(f"  - Correo: '{AXASOAT_CORREO_LOGIN}'")
        logs.append(f"  - Tipo Reclamante: '{AXASOAT_TIPO_RECLAMANTE_LOGIN}'")
        logs.append(f"  - Documento reclamante: '{AXASOAT_DOCUMENTO_LOGIN}'")

        page.wait_for_timeout(1000)
        btn_iniciar = page.locator(AXASOAT_SELECTOR_LOGIN_BOTON)
        btn_iniciar.wait_for(state="visible", timeout=10000)
        btn_iniciar.click()
        logs.append("  - Clic en 'Iniciar sesión'.")

        # 3. Esperar que se autentique directamente (ClaimOnline ya no solicita código OTP)
        logs.append("  - Esperando autenticación directa...")
        for i in range(30):
            page.wait_for_timeout(1000)
            # Verificar si ya entró al dashboard, recepción o desapareció el botón de inicio de sesión
            if (
                "dashboard" in page.url
                or "reception" in page.url
                or page.locator("mok-icon[name='reader-outline']").count() > 0
                or page.locator("button:has-text('Iniciar sesión')").count() == 0
            ):
                logs.append(f"  - Sesión iniciada con éxito. URL actual: {page.url}")
                break
        else:
            logs.append("  - Aviso: Verificando estado de la página tras iniciar sesión...")

        page.wait_for_timeout(2000)
        # Cerrar posible modal de notificación si intercepta
        try:
            btn_close = page.locator("div[class*='z-[999]'] button, div[class*='z-[99999]'] button, mok-modal button").first
            if btn_close.is_visible(timeout=2000):
                btn_close.click(force=True)
        except Exception:
            pass

        # 7. Navegar a Recepción haciendo clic en el icono correspondiente o vía URL
        page.wait_for_timeout(1500)
        try:
            if "recepcion" not in page.url.lower():
                page.goto("https://axa.claimonline.com.co/dashboard/recepcion", timeout=15000)
                logs.append("  - Navegación directa a Recepción.")
        except Exception:
            pass

        # Buscar el botón o tooltip de recepción como respaldo
        boton_recepcion = page.locator("mok-tooltip[data-name-tag='2'], mok-icon[name='reader-outline']").first
        try:
            if boton_recepcion.is_visible(timeout=5000):
                boton_recepcion.click(force=True)
                logs.append("  - Clic en módulo de Recepción.")
        except Exception:
            pass

        # Esperar a que el formulario de recepción cargue efectivamente
        try:
            page.locator(AXASOAT_SELECTOR_FORMULARIO_VERIFY).first.wait_for(state="visible", timeout=25000)
            logs.append("Login exitoso en AXA SOAT y formulario de Recepción cargado.")
        except Exception:
            logs.append("Aviso: Esperando carga final de Recepción...")
            # Reintentar un clic por si acaso
            if page.locator("mok-icon[name='reader-outline']").count() > 0:
                page.locator("mok-icon[name='reader-outline']").first.click(force=True)
            page.locator(AXASOAT_SELECTOR_FORMULARIO_VERIFY).first.wait_for(state="visible", timeout=25000)
            logs.append("Formulario de Recepción verificado tras reintento.")

        return True, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado durante el login en AXA SOAT: {e}"
        logs.append(error_msg); traceback.print_exc()
        log_screenshot = guardar_screenshot_de_error(page, "error_login_axa")
        logs.append(log_screenshot)
        return False, "\n".join(logs)


def asegurar_formulario_limpio(page: Page) -> None:
    """Asegura que el formulario esté en un estado limpio antes de procesar una carpeta."""
    try:
        # 1. Si hay modales abiertos o overlays bloqueando la pantalla (incluido modal informativo de bienvenida/notificación), cerrarlos/eliminarlos
        try:
            # Cerrar botón 'X' o botón de cierre en modales informativos
            btn_close_notif = page.locator("button svg, div[class*='z-[999]'] svg, div[class*='z-[99999]'] svg, svg[data-icon='xmark']").first
            if btn_close_notif.is_visible(timeout=1000):
                btn_close_notif.click(force=True)
                page.wait_for_timeout(500)

            btns = page.locator("div.modal-content button, button:has-text('ACEPTAR'), button:has-text('Aceptar')")
            while btns.count() > 0 and btns.first.is_visible():
                btns.first.click(force=True)
                page.wait_for_timeout(500)
        except Exception:
            pass

        # 2. Recargar completamente el formulario de recepción para reiniciar inputs y archivos adjuntos
        try:
            if "recepcion" in page.url.lower():
                page.reload()
            else:
                page.goto("https://axa.claimhunting.com.co/dashboard/recepcion", timeout=15000)
            page.wait_for_timeout(1500)
        except Exception:
            pass

        # Esperar que cargue el formulario
        try:
            page.locator(AXASOAT_SELECTOR_FORMULARIO_VERIFY).first.wait_for(state="visible", timeout=15000)
        except Exception:
            btn_rec_fallback = page.locator("mok-icon[name='reader-outline']").first
            if btn_rec_fallback.is_visible(timeout=2000):
                btn_rec_fallback.click(force=True)
            else:
                page.goto("https://axa.claimhunting.com.co/dashboard/recepcion", timeout=15000)
            page.locator(AXASOAT_SELECTOR_FORMULARIO_VERIFY).first.wait_for(state="visible", timeout=20000)

        # 3. Limpiar inputs si quedaron restos
        page.evaluate("""() => {
            const inv = document.querySelector("input[name='invoiceNumber']");
            if (inv) {
                inv.value = "";
                inv.dispatchEvent(new Event('input', { bubbles: true }));
                inv.dispatchEvent(new Event('change', { bubbles: true }));
            }
            const nit = document.querySelector("input.input-number-nit");
            if (nit) {
                nit.value = "";
                nit.dispatchEvent(new Event('input', { bubbles: true }));
                nit.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }""")
    except Exception:
        pass

def navegar_a_inicio(page: Page) -> tuple[bool, str]:
    asegurar_formulario_limpio(page)
    return True, "Formulario AXA verificado y listo."

def llenar_formulario(page: Page, codigo_factura: str, subfolder_path: Path | None = None, context: str = 'default') -> tuple[bool, str]:
    """Llena los campos del formulario de radicación de AXA ClaimOnline."""
    logs = ["Llenando formulario de radicación..."]
    try:
        # 1. NIT Ramo SOAT Colpatria (8600021846)
        nit_loc = page.locator("input.input-number-nit, input[placeholder*='NIT ramo SOAT Colpatria']").first
        nit_loc.wait_for(state="visible", timeout=20000)
        nit_loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        nit_loc.fill(str(AXASOAT_NIT_RAMO_FORM))
        nit_loc.dispatch_event("input")
        nit_loc.dispatch_event("change")
        # Asegurar también con evaluate directo
        page.evaluate("""(nitVal) => {
            const el = document.querySelector('input.input-number-nit, input[placeholder*="NIT ramo SOAT Colpatria"]');
            if (el) {
                el.value = nitVal;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }""", str(AXASOAT_NIT_RAMO_FORM))
        logs.append(f"  - NIT Ramo SOAT: {AXASOAT_NIT_RAMO_FORM}")

        # 2. N° Factura
        inv_loc = page.locator("input[name='invoiceNumber']").first
        inv_loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        inv_loc.fill(codigo_factura.upper())
        inv_loc.dispatch_event("input")
        inv_loc.dispatch_event("change")
        # Disparar blur para que la web consulte la API de validación de factura
        inv_loc.evaluate("el => el.blur()")
        logs.append(f"  - N° Factura: {codigo_factura.upper()}")

        # Esperar hasta 5 segundos a que la API responda o aparezca el modal de factura informativa
        for _ in range(10):
            page.wait_for_timeout(350)
            modal_loc = page.locator("div.modal-content").first
            modal_visible = False
            modal_txt = ""
            try:
                if modal_loc.is_visible():
                    modal_visible = True
                    modal_txt = modal_loc.inner_text()
            except Exception:
                pass

            if modal_visible and ("fue recibida" in modal_txt.lower() or "siguiente reclamaci" in modal_txt.lower()):
                logs.append("  - AVISO: Mensaje de 'Factura fue recibida' detectado. Cerrando modal con ACEPTAR para continuar...")
                try:
                    btn_modal_inv = page.locator("div.modal-content button:has-text('ACEPTAR'), div.modal-content button:has-text('Aceptar'), button:has-text('ACEPTAR'), button:has-text('Aceptar')").last
                    if btn_modal_inv.is_visible(timeout=3000):
                        btn_modal_inv.click()
                        logs.append("  - Modal informativo cerrado con clic en ACEPTAR.")
                except Exception:
                    pass
                page.wait_for_timeout(1000)
                try:
                    if page.locator("div.modal-content button").count() > 0:
                        page.locator("div.modal-content button").last.click(force=True)
                except Exception:
                    pass
                break

        # Asegurar que ningún modal residual quedó abierto
        try:
            btn_mod = page.locator("div.modal-content button:has-text('ACEPTAR'), div.modal-content button:has-text('Aceptar')").last
            if btn_mod.is_visible(timeout=1000):
                btn_mod.click()
        except Exception:
            pass
        page.wait_for_timeout(500)

        # 3. Checkbox RIPS desmarcado por defecto si existe
        chk = page.locator("input[type='checkbox'][name*='check_service']")
        if chk.count() > 0 and chk.first.is_checked():
            chk.first.uncheck()
            logs.append("  - Checkbox RIPS desmarcado.")

        # 4. Usuario que registra: clinica asotrauma
        # 4. Usuario que registra: CLINICA ASOTRAUMA (mayúsculas, sin espacios extra)
        usr_nombre = "CLINICA ASOTRAUMA"
        usr_loc = page.locator("input[name='userRegister']").first
        usr_loc.wait_for(state="visible", timeout=10000)
        usr_loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        usr_loc.press_sequentially(usr_nombre, delay=30)
        usr_loc.dispatch_event("input")
        usr_loc.dispatch_event("change")
        usr_loc.evaluate("el => el.blur()")
        page.wait_for_timeout(300)
        logs.append(f"  - Usuario que Registra: {usr_nombre}")

        # 5. Seleccionar Tipo de Cuenta para desplegar sección Soportes
        account_type_val = "REL" if context == "aceptadas" else "OBJ"
        if context == "aceptadas":
            tipo_cuenta_label = AXASOAT_TIPO_CUENTA_FORM_RESPUESTA_LIQUIDACION
            logs.append(f"  - Contexto 'aceptadas' detectado. Tipo de cuenta: '{tipo_cuenta_label}' ({account_type_val})")
        else:
            tipo_cuenta_label = AXASOAT_TIPO_CUENTA_FORM_RESPUESTA_OBJECION
            logs.append(f"  - Usando Tipo de cuenta por defecto: '{tipo_cuenta_label}' ({account_type_val})")

        # Clic en el select/dropdown de tipo de cuenta
        tipo_cta_input = page.locator("input[data-analytics='input-select-accountType'], input[placeholder='Seleccione una opción']").first
        tipo_cta_input.click()
        page.wait_for_timeout(500)

        # Buscar la opción correspondiente en el desplegable
        palabra_clave = "liquidaci" if context == "aceptadas" else "objeci"
        opcion_locator = page.locator(f"text=/{palabra_clave}/i").last
        if opcion_locator.is_visible(timeout=3000):
            opcion_locator.click()
            logs.append(f"  - Tipo de cuenta seleccionado: '{tipo_cuenta_label}'")
        else:
            page.locator(f"div:has-text('{tipo_cuenta_label}'), span:has-text('{tipo_cuenta_label}'), li:has-text('{tipo_cuenta_label}')").last.click()
            logs.append(f"  - Tipo de cuenta seleccionado vía texto: '{tipo_cuenta_label}'")

        page.wait_for_timeout(500)

        # Sincronización exacta con los Hooks del componente ReceptionPage:
        # Hook 6:  [rt, at] = useState({}) (Errores de formulario) -> at({})
        # Hook 8:  [yt, gt] = useState(!1) (hasRips) -> gt(false)
        # Hook 11: [Ct, vt] = useState({}) (Errores RIPS) -> vt({})
        # Hook 16: [Vt, Wt] = useState(0) (accountType Value) -> Wt(account_type_val)
        # Hook 17: [kt, Mt] = useState(formData) -> Mt(...)
        try:
            page.evaluate("""(data) => {
                const root = document.querySelector('#root') || document.body;
                const reactKey = Object.keys(root).find(k => k.startsWith('__reactContainer') || k.startsWith('__reactFiber'));
                let fiber = root[reactKey];
                let receptionFiber = null;
                function findReception(node) {
                    if (!node || receptionFiber) return;
                    let m = node.memoizedState;
                    while (m) {
                        if (m.memoizedState && typeof m.memoizedState === 'object' && 'accountType' in m.memoizedState && 'nit' in m.memoizedState) {
                            receptionFiber = node;
                            return;
                        }
                        m = m.next;
                    }
                    findReception(node.child);
                    findReception(node.sibling);
                }
                findReception(fiber);
                if (receptionFiber) {
                    let cur = receptionFiber.memoizedState;
                    let idx = 0;
                    let hook6 = null;
                    let hook8 = null;
                    let hook11 = null;
                    let hook16 = null;
                    let hook17 = null;
                    while (cur) {
                        if (idx === 6) hook6 = cur;
                        if (idx === 8) hook8 = cur;
                        if (idx === 11) hook11 = cur;
                        if (idx === 16) hook16 = cur;
                        if (idx === 17) hook17 = cur;
                        cur = cur.next;
                        idx++;
                    }
                    if (hook6 && hook6.queue) {
                        hook6.queue.dispatch({});
                    }
                    if (hook8 && hook8.queue) {
                        hook8.queue.dispatch(false);
                    }
                    if (hook11 && hook11.queue) {
                        hook11.queue.dispatch({});
                    }
                    if (hook16 && hook16.queue) {
                        hook16.queue.dispatch(data.accountTypeVal);
                    }
                    if (hook17 && hook17.queue) {
                        hook17.queue.dispatch(prev => ({
                            ...prev,
                            nit: "8600021846",
                            invoiceNumber: String(data.invoice || ''),
                            userRegister: String(data.user || ''),
                            accountType: String(data.accountTypeVal || '')
                        }));
                    }
                }
            }""", {"invoice": codigo_factura.upper(), "user": usr_nombre, "accountTypeVal": account_type_val})
            page.wait_for_timeout(300)
        except Exception:
            pass

        logs.append("Formulario llenado con éxito y sección de Soportes habilitada.")
        return True, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR inesperado al llenar el formulario de AXA: {e}"
        logs.append(error_msg); traceback.print_exc()
        log_screenshot = guardar_screenshot_de_error(page, "error_formulario_axa")
        logs.append(log_screenshot)
        return False, "\n".join(logs)

def asegurar_extension_pdf_minuscula(pdf_path: Path) -> tuple[Path, str]:
    """
    Verifica si un archivo PDF tiene la extensión en mayúsculas (.PDF)
    y, si es así, lo renombra a minúsculas (.pdf).
    
    Devuelve la ruta final (ya sea la original o la nueva) y un log.
    """
    logs = [f"  Verificando extensión del archivo: {pdf_path.name}..."]
    if not pdf_path.is_file():
        return pdf_path, f"  ERROR: El archivo de respuesta no existe en la ruta {pdf_path}."

    if pdf_path.suffix == ".PDF":
        nuevo_path = pdf_path.with_suffix(".pdf")
        try:
            pdf_path.rename(nuevo_path)
            logs.append(f"  -> Renombrado: '{pdf_path.name}' -> '{nuevo_path.name}'")
            return nuevo_path, "\n".join(logs)
        except OSError as e:
            error_msg = f"  -> ERROR al renombrar el archivo: {e}"
            logs.append(error_msg)
            return pdf_path, "\n".join(logs) # Devolvemos la ruta original en caso de error
    else:
        logs.append("  -> Extensión ya es minúscula. No se requiere acción.")
        return pdf_path, "\n".join(logs)

def subir_archivo_respuesta(page: Page, pdf_path: Path) -> tuple[bool, str]:
    """Sube el archivo de respuesta de glosa en el input Otros (others) de la sección Soportes."""
    logs = [f"  Subiendo archivo de respuesta: {pdf_path.name}..."]
    try:
        # El input file ahora es input[type='file'][name='others']
        input_file = page.locator("input[type='file'][name='others'], input[type='file'][accept*='.pdf']").first
        input_file.set_input_files(pdf_path)
        page.wait_for_timeout(2000)

        # Disparar en el elemento Web Component y en el input interno
        page.evaluate("""() => {
            const inp = document.querySelector("input[type='file'][name='others']") || document.querySelector("input[type='file']");
            if (inp && inp.files && inp.files.length > 0) {
                const fileObj = inp.files[0];
                const filePayload = {
                    event: [fileObj],
                    previewUrl: null,
                    filesPreview: [fileObj.name],
                    countFiles: 1
                };

                // 1. Invocar en mok-input-multiplefiles si existe el método processFiles
                const mokMultiple = inp.closest('mok-input-multiplefiles');
                if (mokMultiple) {
                    if (typeof mokMultiple.processFiles === 'function') {
                        try { mokMultiple.processFiles([fileObj]); } catch(e){}
                    }
                    if (mokMultiple.eventChange && typeof mokMultiple.eventChange.emit === 'function') {
                        try { mokMultiple.eventChange.emit(filePayload); } catch(e){}
                    }
                }

                // 2. Invocar en mok-form-constructor handleCahngeInput
                const mokForm = inp.closest('mok-form-constructor');
                if (mokForm) {
                    if (typeof mokForm.handleCahngeInput === 'function') {
                        try {
                            mokForm.handleCahngeInput({ detail: filePayload }, 'others', 'multipleFiles');
                        } catch(e){}
                    }
                    if (typeof mokForm.eventInput === 'function') {
                        try {
                            mokForm.eventInput({ detail: filePayload, name: 'others', type: 'multipleFiles' });
                        } catch(e){}
                    }
                }

                // 3. Dispatch standard events
                inp.dispatchEvent(new Event('change', { bubbles: true }));
                inp.dispatchEvent(new Event('input', { bubbles: true }));

                // 4. Sincronización directa en el Fiber de Recepción:
                // Hook 6: at({}) (errores limpios)
                // Hook 15: Ft(true) (hasFiles = true)
                // Hook 17: Mt(prev => ({ ...prev, others: filePayload }))
                const root = document.querySelector('#root') || document.body;
                const reactKey = Object.keys(root).find(k => k.startsWith('__reactContainer') || k.startsWith('__reactFiber'));
                let fiber = root[reactKey];
                let receptionFiber = null;

                function findReception(node) {
                    if (!node || receptionFiber) return;
                    let m = node.memoizedState;
                    while (m) {
                        if (m.memoizedState && typeof m.memoizedState === 'object' && 'accountType' in m.memoizedState && 'nit' in m.memoizedState) {
                            receptionFiber = node;
                            return;
                        }
                        m = m.next;
                    }
                    findReception(node.child);
                    findReception(node.sibling);
                }
                findReception(fiber);

                if (receptionFiber) {
                    let cur = receptionFiber.memoizedState;
                    let idx = 0;
                    while (cur) {
                        if (idx === 6 && cur.queue) {
                            cur.queue.dispatch({});
                        }
                        if (idx === 15 && cur.queue) {
                            cur.queue.dispatch(true);
                        }
                        if (idx === 17 && cur.queue) {
                            cur.queue.dispatch(prev => ({
                                ...prev,
                                others: filePayload
                            }));
                        }
                        cur = cur.next;
                        idx++;
                    }
                }
            }
        }""")
        page.wait_for_timeout(1000)
        logs.append("  -> Archivo adjuntado correctamente en Soportes.")
        return True, "\n".join(logs)
    except Exception as e:
        error_msg = f"  -> ERROR al subir el archivo: {e}"
        logs.append(error_msg); traceback.print_exc()
        log_screenshot = guardar_screenshot_de_error(page, "error_subida_archivo_axa")
        logs.append(log_screenshot)
        return False, "\n".join(logs)

def procesar_carpeta(page: Page, subfolder_path: Path, subfolder_name: str, context: str = 'default') -> tuple[str, str | None, str | None, str]:
    """
    Orquestador web para AXA: filtra, valida, llena formulario, sube soportes y envía.
    Captura el radicado del modal/red y guarda el pantallazo de radicación en la subcarpeta.
    """
    logs = [f"--- Iniciando procesamiento WEB para AXA | Carpeta: '{subfolder_name}' ---"]
    try:
        # 1. Verificar por nombre de carpeta
        palabras_encontradas = [p for p in PALABRAS_EXCLUSION_CARPETAS if p in subfolder_name.upper()]
        if palabras_encontradas:
            motivo = ", ".join(palabras_encontradas)
            msg = f"OMITIENDO: El nombre contiene la(s) palabra(s) de exclusión: '{motivo}'."
            logs.append(msg)
            return ESTADO_OMITIDO_RADICADO, None, None, "\n".join(logs)

        # 2. Verificar si ya está radicada
        if any(f.name.lower().endswith("-recibido.pdf") or "-radicado" in f.name.lower() for f in subfolder_path.iterdir() if f.is_file()):
            msg = "OMITIENDO: Ya existe un archivo de radicado previo en la carpeta."
            logs.append(msg)
            return ESTADO_OMITIDO_RADICADO, None, None, "\n".join(logs)

        # 3. Búsqueda y preparación de archivos
        codigo_factura, pdf_path, pdf_log = encontrar_y_validar_pdfs(subfolder_path, subfolder_name, AXASOAT_NOMBRE_EN_PDF)
        logs.append(pdf_log)
        if not (codigo_factura and pdf_path):
            return ESTADO_FALLO, None, None, "\n".join(logs)
        
        path_pdf_final, rename_log = asegurar_extension_pdf_minuscula(pdf_path)
        logs.append(rename_log)

        # 4. Interacción Web
        asegurar_formulario_limpio(page)
        form_ok, form_log = llenar_formulario(page, codigo_factura, subfolder_path=subfolder_path, context=context)
        logs.append(form_log)
        if not form_ok:
            asegurar_formulario_limpio(page)
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

        upload_ok, upload_log = subir_archivo_respuesta(page, path_pdf_final)
        logs.append(upload_log)
        if not upload_ok:
            asegurar_formulario_limpio(page)
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
            
        radicado_final, final_log = enviar_y_finalizar_radicado(page, subfolder_path, codigo_factura)
        logs.append(final_log)
        if not radicado_final:
            asegurar_formulario_limpio(page)
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
            
        logs.append(f"--- Proceso web para '{subfolder_name}' finalizado con ÉXITO. Radicado: {radicado_final} ---")
        return ESTADO_EXITO, radicado_final, codigo_factura, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR CRÍTICO en AXA/procesar_carpeta: {e}"
        traceback.print_exc()
        asegurar_formulario_limpio(page)
        return ESTADO_FALLO, None, None, "\n".join(logs + [error_msg])

def enviar_y_finalizar_radicado(page: Page, subfolder_path: Path, codigo_factura: str) -> tuple[str | None, str]:
    """
    Hace clic en 'Guardar información', intercepta el response de reception,
    espera el modal de confirmación, guarda el screenshot en la carpeta y extrae el radicado.
    """
    logs = ["  Finalizando el proceso de radicación..."]
    radicado_extraido = None
    response_radicado = []

    def on_response(res):
        if "reception" in res.url:
            try:
                txt = res.text()
                # Ejemplo: "Ok Reclamación creada con éxito 23237945|23237945" o JSON {"claimId": 23237945}
                m = re.search(r"creada\s+con\s+[eé]xito\s+(\d+)", txt, re.IGNORECASE) or \
                    re.search(r"Ok.*?(\d{7,10})", txt, re.IGNORECASE)
                if m:
                    response_radicado.append(m.group(1))
            except Exception:
                pass

    page.on("response", on_response)

    try:
        # Si hay un modal abierto previo bloqueando la pantalla, cerrarlo
        try:
            btn_prev = page.locator("div.modal-content button:has-text('ACEPTAR'), div.modal-content button:has-text('Aceptar'), button:has-text('ACEPTAR')")
            if btn_prev.is_visible(timeout=2000):
                btn_prev.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        # Sincronizar y limpiar estado de validación inmediatamente antes de dar clic en Guardar
        try:
            page.evaluate("""(data) => {
                const root = document.querySelector('#root') || document.body;
                const reactKey = Object.keys(root).find(k => k.startsWith('__reactContainer') || k.startsWith('__reactFiber'));
                let fiber = root[reactKey];
                let receptionFiber = null;
                function findReception(node) {
                    if (!node || receptionFiber) return;
                    let m = node.memoizedState;
                    while (m) {
                        if (m.memoizedState && typeof m.memoizedState === 'object' && 'accountType' in m.memoizedState && 'nit' in m.memoizedState) {
                            receptionFiber = node;
                            return;
                        }
                        m = m.next;
                    }
                    findReception(node.child);
                    findReception(node.sibling);
                }
                findReception(fiber);
                if (receptionFiber) {
                    let cur = receptionFiber.memoizedState;
                    let idx = 0;
                    while (cur) {
                        // Hook 6: [rt, at] (form errors) -> clear completely
                        if (idx === 6 && cur.queue) {
                            cur.queue.dispatch({});
                        }
                        // Hook 8: [yt, gt] (hasRips) -> false
                        if (idx === 8 && cur.queue) {
                            cur.queue.dispatch(false);
                        }
                        // Hook 11: [Ct, vt] (rips errors) -> clear completely
                        if (idx === 11 && cur.queue) {
                            cur.queue.dispatch({});
                        }
                        // Hook 15: [Nt, Ft] (hasFiles) -> true
                        if (idx === 15 && cur.queue) {
                            cur.queue.dispatch(true);
                        }
                        // Hook 16: [Vt, Wt] (accountType ID/Value)
                        if (idx === 16 && cur.queue) {
                            cur.queue.dispatch("OBJ");
                        }
                        // Hook 17: [kt, Mt] (formData)
                        if (idx === 17 && cur.queue) {
                            cur.queue.dispatch(prev => {
                                const base = prev || {};
                                return {
                                    ...base,
                                    nit: "8600021846",
                                    invoiceNumber: String(data.invoice || ''),
                                    userRegister: "CLINICA ASOTRAUMA",
                                    accountType: base.accountType || "OBJ"
                                };
                            });
                        }
                        cur = cur.next;
                        idx++;
                    }
                }
            }""", {"invoice": codigo_factura.upper()})
            page.wait_for_timeout(300)
        except Exception:
            pass

        # Clic en 'Guardar información' (una sola vez)
        boton_guardar = page.locator("button:has-text('Guardar información')").last
        boton_guardar.wait_for(state="visible", timeout=10000)
        boton_guardar.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        boton_guardar.click()
        logs.append("  -> Clic en 'Guardar información'.")

        # Esperar a que el modal de carga 'Se está enviando la información' desaparezca y aparezca el modal con el resultado
        logs.append("  -> Esperando procesamiento del envío...")
        for _ in range(60):
            page.wait_for_timeout(1000)
            txt_actual = ""
            try:
                txt_actual = page.locator("div.modal-content, #modal-container").first.inner_text()
            except Exception:
                pass
            if "enviando la información" not in txt_actual.lower() and ("creada con éxito" in txt_actual.lower() or "importante" in txt_actual.lower() or response_radicado):
                break

        page.wait_for_timeout(2000)

        # 1. Extraer número de radicado del modal
        modal_text = ""
        try:
            modal_loc = page.locator("div.modal-content").first
            if modal_loc.is_visible():
                modal_text = modal_loc.inner_text()
        except Exception:
            pass

        # Verificar si fue un modal de error o de advertencia no exitoso
        if "Verifique los campos requeridos" in modal_text or "error al enviar la información" in modal_text.lower() or "typeerror" in modal_text.lower():
            logs.append(f"  -> ERROR en el envío/validación del formulario: {modal_text.strip()}")
            log_shot = guardar_screenshot_de_error(page, f"error_envio_{codigo_factura}")
            logs.append(log_shot)
            try:
                btn_err = page.locator("div.modal-content button:has-text('Aceptar'), div.modal-content button:has-text('ACEPTAR'), button:has-text('Aceptar')").last
                if btn_err.is_visible(timeout=2000):
                    btn_err.click()
            except Exception:
                pass
            return None, "\n".join(logs)

        # Buscar estrictamente el radicado de reclamación creada con éxito (con checkmark azul)
        match = re.search(r"Reclamaci[oó]n\s+creada\s+con\s+[eé]xito\s+(\d+)", modal_text, re.IGNORECASE) or \
                re.search(r"creada\s+con\s+[eé]xito\s*[:#-]?\s*(\d+)", modal_text, re.IGNORECASE)

        if match:
            radicado_extraido = match.group(1)
        elif response_radicado:
            radicado_extraido = response_radicado[-1]
        else:
            # Fallback en el DOM completo únicamente para 'creada con éxito'
            txt_body = page.inner_text("body")
            m_body = re.search(r"Reclamaci[oó]n\s+creada\s+con\s+[eé]xito\s+(\d+)", txt_body, re.IGNORECASE)
            if m_body:
                radicado_extraido = m_body.group(1)

        if radicado_extraido:
            logs.append(f"  -> ¡ÉXITO! Radicado obtenido: {radicado_extraido}")
            try:
                nombre_pdf = f"{codigo_factura}-radicado-{radicado_extraido}.pdf"
                ruta_pdf = subfolder_path / nombre_pdf
                temp_png = subfolder_path / f"temp_{codigo_factura}_{radicado_extraido}.png"
                page.screenshot(path=str(temp_png))
                
                # Convertir a PDF (captura de pantalla del modal con el checkmark)
                img = Image.open(temp_png).convert("RGB")
                img.save(ruta_pdf, "PDF")
                try:
                    temp_png.unlink()
                except Exception:
                    pass
                logs.append(f"  -> Comprobante de radicación guardado como PDF en: '{ruta_pdf.name}'")
            except Exception as e_shot:
                logs.append(f"  -> Aviso al guardar PDF de radicación: {e_shot}")

            # Descargar también el soporte oficial con sello que envía AXA al correo
            correo_ok, correo_log = descargar_soporte_radicado_correo(radicado_extraido, subfolder_path, timeout=30)
            logs.append(correo_log)
        else:
            logs.append(f"  -> ERROR: No se generó número de radicado. Mensaje en pantalla: {modal_text.strip() or 'Campos incompletos o inválidos'}")
            log_shot = guardar_screenshot_de_error(page, f"error_radicacion_{codigo_factura}")
            logs.append(log_shot)

        # 3. Hacer clic en 'Aceptar' para cerrar el modal de éxito
        try:
            btn_aceptar = page.locator("div.modal-content button:has-text('Aceptar'), button:has-text('ACEPTAR')").last
            if btn_aceptar.is_visible(timeout=3000):
                btn_aceptar.click()
                logs.append("  -> Clic en 'Aceptar' del modal de éxito.")
        except Exception:
            pass

        page.wait_for_timeout(2000)
        asegurar_formulario_limpio(page)
        return radicado_extraido, "\n".join(logs)

    except Exception as e:
        error_msg = f"  -> ERROR en la finalización: {e}"; traceback.print_exc()
        log_screenshot = guardar_screenshot_de_error(page, "error_finalizacion_axa")
        logs.append(log_screenshot)
        asegurar_formulario_limpio(page)
        return radicado_extraido, "\n".join(logs + [error_msg])
    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:
            pass