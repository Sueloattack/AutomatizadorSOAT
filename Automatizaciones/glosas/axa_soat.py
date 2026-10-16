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
            # Buscar botón X o de cierre
            page.evaluate("""() => {
                const btnX = document.querySelector('div[class*="z-[999]"] button, div[class*="z-[99999]"] button');
                if (btnX) btnX.click();
                document.querySelectorAll('mok-modal, div[class*="z-[999]"], div[class*="z-[99999]"], div[class*="backdrop-blur"]').forEach(el => el.remove());
            }""")
        except Exception:
            pass

        # 7. Navegar a Recepción haciendo clic en el icono correspondiente o vía URL
        page.wait_for_timeout(1500)
        try:
            if "reception" not in page.url:
                page.goto("https://axa.claimhunting.com.co/reception", timeout=15000)
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
            page.evaluate("""() => {
                document.querySelectorAll('mok-modal, div.modal-content, div[class*="backdrop-blur"], div[class*="z-[999]"], div[class*="z-[99999]"]').forEach(el => el.remove());
            }""")
        except Exception:
            pass

        # 2. Navegar al módulo de Recepción para recargar el formulario en limpio
        try:
            # Si estamos en dashboard o cualquier otra página, o para refrescar recepción:
            btn_rec = page.locator("mok-icon[name='reader-outline'], mok-tooltip[data-name-tag='2']").first
            if btn_rec.is_visible(timeout=2000):
                btn_rec.click(force=True)
                page.wait_for_timeout(1000)
            else:
                page.goto("https://axa.claimhunting.com.co/reception", timeout=15000)
                page.wait_for_timeout(1000)
                btn_rec2 = page.locator("mok-icon[name='reader-outline'], mok-tooltip[data-name-tag='2']").first
                if btn_rec2.is_visible(timeout=2000):
                    btn_rec2.click(force=True)
        except Exception:
            pass

        # Esperar que cargue el formulario
        try:
            page.locator(AXASOAT_SELECTOR_FORMULARIO_VERIFY).first.wait_for(state="visible", timeout=15000)
        except Exception:
            # Reintentar clic en el icono del lector
            btn_rec_fallback = page.locator("mok-icon[name='reader-outline']").first
            if btn_rec_fallback.is_visible(timeout=2000):
                btn_rec_fallback.click(force=True)
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
        # 1. NIT Ramo SOAT Colpatria
        nit_loc = page.locator("input.input-number-nit, input[placeholder*='NIT ramo SOAT Colpatria']").first
        nit_loc.wait_for(state="visible", timeout=20000)
        nit_loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(AXASOAT_NIT_RAMO_FORM, delay=20)
        page.keyboard.press("Tab")
        logs.append(f"  - NIT Ramo SOAT: {AXASOAT_NIT_RAMO_FORM}")

        # 2. N° Factura
        inv_loc = page.locator("input[name='invoiceNumber']").first
        inv_loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(codigo_factura.upper(), delay=20)
        page.keyboard.press("Tab")
        logs.append(f"  - N° Factura: {codigo_factura.upper()}")
        page.wait_for_timeout(1000)

        # Si aparece el modal informativo de la factura ("La Factura ... fue recibida ... con la siguiente reclamación ...")
        try:
            modal_loc = page.locator("div.modal-content").first
            if modal_loc.is_visible(timeout=3000):
                modal_txt = modal_loc.inner_text()
                if "fue recibida" in modal_txt.lower() or "siguiente reclamaci" in modal_txt.lower():
                    m_rec = re.search(r"reclamaci[oó]n\s*[:#-]?\s*(\d{7,10})", modal_txt, re.IGNORECASE) or \
                            re.search(r"(\d{7,10})", modal_txt)
                    rad_ya_recibido = m_rec.group(1) if m_rec else "RECIBIDA"
                    logs.append(f"  - AVISO: Factura ya recibida previamente por AXA. Radicado: {rad_ya_recibido}")
                    # Guardar comprobante de radicado previo si no existe
                    try:
                        nombre_pdf = f"{codigo_factura}-radicado-{rad_ya_recibido}.pdf"
                        ruta_pdf = subfolder_path / nombre_pdf
                        if not ruta_pdf.exists():
                            temp_png = subfolder_path / f"temp_{codigo_factura}_{rad_ya_recibido}.png"
                            page.screenshot(path=str(temp_png))
                            img = Image.open(temp_png).convert("RGB")
                            img.save(ruta_pdf, "PDF")
                            try:
                                temp_png.unlink()
                            except Exception:
                                pass
                            logs.append(f"  -> Comprobante de radicación previa guardado como PDF en: '{ruta_pdf.name}'")
                    except Exception:
                        pass

                    btn_modal_inv = page.locator("button:has-text('ACEPTAR'), button:has-text('Aceptar')")
                    if btn_modal_inv.is_visible(timeout=2000):
                        btn_modal_inv.click()
                        logs.append("  - Modal informativo de factura cerrado.")
                        page.wait_for_timeout(500)
                    page.evaluate("""() => {
                        document.querySelectorAll('mok-modal, div.modal-content, div[class*="backdrop-blur"], div[class*="z-[800]"]').forEach(el => el.remove());
                    }""")
                    return True, f"ALREADY_RECEIVED:{rad_ya_recibido}\n" + "\n".join(logs)

                btn_modal_inv = page.locator("button:has-text('ACEPTAR'), button:has-text('Aceptar')")
                if btn_modal_inv.is_visible(timeout=2000):
                    btn_modal_inv.click()
                    logs.append("  - Modal informativo de factura cerrado.")
                    page.wait_for_timeout(500)
                page.evaluate("""() => {
                    document.querySelectorAll('mok-modal, div.modal-content, div[class*="backdrop-blur"], div[class*="z-[800]"]').forEach(el => el.remove());
                }""")
        except Exception:
            pass

        # 3. Checkbox RIPS desmarcado por defecto si existe
        chk = page.locator("input[type='checkbox'][name*='check_service']")
        if chk.count() > 0 and chk.first.is_checked():
            chk.first.uncheck()
            logs.append("  - Checkbox RIPS desmarcado.")

        # 4. Usuario que registra: CLINICA ASOTRAUMA (mayúsculas)
        usr_nombre = AXASOAT_USUARIO_REGISTRA_FORM.upper()
        usr_loc = page.locator("input[name='userRegister']").first
        usr_loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(usr_nombre, delay=20)
        page.keyboard.press("Tab")
        logs.append(f"  - Usuario que Registra: {usr_nombre}")

        # 5. Seleccionar Tipo de Cuenta al final para desplegar sección Soportes
        if context == "aceptadas":
            tipo_cuenta_label = AXASOAT_TIPO_CUENTA_FORM_RESPUESTA_LIQUIDACION
            logs.append(f"  - Contexto 'aceptadas' detectado. Tipo de cuenta: '{tipo_cuenta_label}'")
        else:
            tipo_cuenta_label = AXASOAT_TIPO_CUENTA_FORM_RESPUESTA_OBJECION
            logs.append(f"  - Usando Tipo de cuenta por defecto: '{tipo_cuenta_label}'")

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

        page.wait_for_timeout(1000)

        # Sincronización robusta: Inyectar directamente en el estado de React (Fiber) del componente de Recepción
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
                while (cur) {
                    if (cur.memoizedState && typeof cur.memoizedState === 'object') {
                        // 1. Hook de datos del formulario (kt)
                        if ('nit' in cur.memoizedState && typeof cur.memoizedState.nit === 'string') {
                            cur.queue.dispatch(prev => ({
                                ...prev,
                                nit: String(data.nit || ''),
                                invoiceNumber: String(data.invoice || ''),
                                userRegister: String(data.user || ''),
                                accountType: prev && prev.accountType ? String(prev.accountType) : String(data.accountType || '')
                            }));
                        }
                        // 2. Hook de errores del formulario (rt)
                        if (cur.memoizedState && (cur.memoizedState.nit || cur.memoizedState.invoiceNumber || cur.memoizedState.userRegister)) {
                            let nextErr = { ...cur.memoizedState };
                            delete nextErr.nit;
                            delete nextErr.invoiceNumber;
                            delete nextErr.userRegister;
                            cur.queue.dispatch(nextErr);
                        }
                    }
                    cur = cur.next;
                }
            }

            // Actualizar visualmente los inputs del DOM
            const nitInp = document.querySelector('input.input-number-nit');
            if (nitInp) nitInp.value = data.nit;
            const invInp = document.querySelector('input[name="invoiceNumber"]');
            if (invInp) invInp.value = data.invoice;
            const usrInp = document.querySelector('input[name="userRegister"]');
            if (usrInp) usrInp.value = data.user;
        }""", {"nit": AXASOAT_NIT_RAMO_FORM, "invoice": codigo_factura.upper(), "user": usr_nombre, "accountType": tipo_cuenta_label})

        page.wait_for_timeout(1000)
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

        # Trigger React upload handler y asegurar que Nt se establezca en true (Dt(true))
        page.evaluate("""() => {
            const inp = document.querySelector("input[type='file'][name='others']");
            if (inp && inp.files && inp.files.length > 0) {
                inp.dispatchEvent(new Event('change', { bubbles: true }));
                inp.dispatchEvent(new Event('input', { bubbles: true }));
            }

            // Forzar en el Fiber de Recepción que Nt (hasFiles / others uploaded) sea true
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
                    // Hook index 15 es [Nt, Dt] = useState(false)
                    if (idx === 15 && typeof cur.memoizedState === 'boolean') {
                        cur.queue.dispatch(true);
                    }
                    // Hook index 6 es [rt, at] = useState({}) errores
                    if (idx === 6 && cur.memoizedState && typeof cur.memoizedState === 'object') {
                        let nextErr = { ...cur.memoizedState };
                        delete nextErr.others;
                        delete nextErr.pdf;
                        delete nextErr.nit;
                        cur.queue.dispatch(nextErr);
                    }
                    cur = cur.next;
                    idx++;
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

        # Si la factura ya había sido recibida previamente por AXA
        if "ALREADY_RECEIVED:" in form_log:
            m_rad = re.search(r"ALREADY_RECEIVED:(\d+)", form_log)
            rad_prev = m_rad.group(1) if m_rad else "RECIBIDA"
            asegurar_formulario_limpio(page)
            logs.append(f"--- Factura '{codigo_factura}' ya recibida previamente con radicado: {rad_prev} ---")
            return ESTADO_EXITO, rad_prev, codigo_factura, "\n".join(logs)

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

        # Verificar si fue un modal de error
        if "Verifique los campos requeridos" in modal_text or "error al enviar la información" in modal_text.lower() or "typeerror" in modal_text.lower():
            logs.append(f"  -> ERROR en el envío/validación del formulario: {modal_text.strip()}")
            log_shot = guardar_screenshot_de_error(page, f"error_envio_{codigo_factura}")
            logs.append(log_shot)
            try:
                page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('div.modal-content button, button')).filter(b => b.textContent && (b.textContent.includes('Aceptar') || b.textContent.includes('ACEPTAR')));
                    if (btns.length > 0) btns[btns.length - 1].click();
                    document.querySelectorAll('mok-modal, div.modal-content, div[class*="backdrop-blur"], div[class*="z-[800]"], div[class*="z-[999]"]').forEach(el => el.remove());
                }""")
            except Exception:
                pass
            return None, "\n".join(logs)

        match = re.search(r"Reclamaci[oó]n\s+creada\s+con\s+[eé]xito\s+(\d+)", modal_text, re.IGNORECASE) or \
                re.search(r"creada\s+con\s+[eé]xito\s*[:#-]?\s*(\d+)", modal_text, re.IGNORECASE) or \
                re.search(r"siguiente\s+reclamaci[oó]n\s+(\d+)", modal_text, re.IGNORECASE) or \
                re.search(r"reclamaci[oó]n\s*[:#-]?\s*(\d{7,10})", modal_text, re.IGNORECASE)

        if match:
            radicado_extraido = match.group(1)
        elif response_radicado:
            radicado_extraido = response_radicado[-1]
        else:
            # Fallback en el DOM completo
            txt_body = page.inner_text("body")
            m_body = re.search(r"Reclamaci[oó]n\s+creada\s+con\s+[eé]xito\s+(\d+)", txt_body, re.IGNORECASE) or \
                     re.search(r"siguiente\s+reclamaci[oó]n\s+(\d+)", txt_body, re.IGNORECASE)
            if m_body:
                radicado_extraido = m_body.group(1)

        if radicado_extraido:
            logs.append(f"  -> ¡ÉXITO! Radicado obtenido: {radicado_extraido}")
            try:
                nombre_pdf = f"{codigo_factura}-radicado-{radicado_extraido}.pdf"
                ruta_pdf = subfolder_path / nombre_pdf
                temp_png = subfolder_path / f"temp_{codigo_factura}_{radicado_extraido}.png"
                page.screenshot(path=str(temp_png))
                
                # Convertir a PDF
                img = Image.open(temp_png).convert("RGB")
                img.save(ruta_pdf, "PDF")
                try:
                    temp_png.unlink()
                except Exception:
                    pass
                logs.append(f"  -> Comprobante de radicación guardado como PDF en: '{ruta_pdf.name}'")
            except Exception as e_shot:
                logs.append(f"  -> Aviso al guardar PDF de radicación: {e_shot}")
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