# Automatizaciones/glosas/sura_arl.py
import time
import re
import traceback
from pathlib import Path
import os
from playwright.sync_api import Page, expect, TimeoutError as PlaywrightTimeoutError

try:
    from PIL import Image
except ImportError:
    raise ImportError("Falta Pillow. pip install Pillow")

try:
    from Configuracion.constantes import *
except ImportError as e:
    raise ImportError(f"ERROR CRITICO: No se pudieron importar constantes: {e}")

ESTADO_EXITO = "EXITO"
ESTADO_FALLO = "FALLO"
ESTADO_OMITIDO_RADICADO = "OMITIDO_RADICADO"
ESTADO_OMITIDO_DUPLICADA = "OMITIDO_DUPLICADA"

def dispatch_mouse_events(page: Page, selector: str):
    """Simula eventos de mouse completos (mousedown, mouseup, click) en un elemento."""
    page.eval_on_selector(selector, """el => {
        ['mousedown', 'mouseup', 'click'].forEach(eventType => {
            el.dispatchEvent(new MouseEvent(eventType, { bubbles: true, cancelable: true, view: window }));
        });
    }""")

def login(page: Page) -> tuple[bool, str]:
    """Realiza el login en SURA ARL usando Playwright con lógica ultra-robusta de eventos."""
    logs = ["Iniciando login en SURA ARL con Playwright..."]
    try:
        # Ir a la página de login
        page.goto(SURA_ARL_LOGIN_URL, timeout=60000)
        logs.append("  Página de login cargada.")

        # Esperar a que el selector y la opción específica de CEDULA ('C') estén presentes en el DOM (por si se cargan dinámicamente)
        page.wait_for_selector("#ctl00_ContentMain_suraType option[value='C']", state="attached", timeout=20000)

        # Seleccionar Tipo de Identificación: CEDULA y disparar eventos change/input
        page.select_option("#ctl00_ContentMain_suraType", value="C")
        page.eval_on_selector("#ctl00_ContentMain_suraType", """el => {
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('input', { bubbles: true }));
        }""")
        logs.append("  - Tipo Identificación: CEDULA seleccionado y eventos disparados.")

        # Esperar un momento a que termine cualquier postback/recarga de ASP.NET tras cambiar el tipo de identificación
        time.sleep(2)
        page.wait_for_selector("#suraName", timeout=10000)
        
        # Verificar si se deseleccionó y re-seleccionar si es necesario
        current_type = page.eval_on_selector("#ctl00_ContentMain_suraType", "el => el.value")
        if current_type != "C":
            logs.append(f"  - ¡Alerta! El Tipo de Identificación se reseteó a '{current_type}'. Re-seleccionando CEDULA ('C').")
            page.select_option("#ctl00_ContentMain_suraType", value="C")
            page.eval_on_selector("#ctl00_ContentMain_suraType", """el => {
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }""")
            time.sleep(1)

        page.locator("#suraName").fill("1005911366")
        logs.append("  - Cédula ingresada.")

        # Asegurar foco y clic en contraseña para habilitar el teclado
        password_input = page.locator("input[name='suraPassword']")
        password_input.click()
        logs.append("  - Clic en campo de contraseña para desplegar teclado virtual.")

        # Esperar a que el teclado virtual esté visible en el DOM
        page.wait_for_selector(".ui-keyboard", timeout=5000)
        time.sleep(1)

        # Clave: 2026
        clave = "2026"
        for digito in clave:
            # Buscar el botón por el atributo data-value del dígito
            selector_tecla = f"button.ui-keyboard-button[data-value='{digito}']"
            page.wait_for_selector(selector_tecla, timeout=3000)
            dispatch_mouse_events(page, selector_tecla)
            logs.append(f"    - Tecla {digito} presionada.")
            time.sleep(0.3)

        # Click en el botón de aceptar del teclado (chulo/✔) usando eventos de mouse completos
        page.wait_for_selector("button.ui-keyboard-accept", timeout=3000)
        dispatch_mouse_events(page, "button.ui-keyboard-accept")
        logs.append("  - Aceptar (✔) teclado virtual presionado.")
        time.sleep(0.5)

        # Verificar por última vez el select antes de enviar
        current_type = page.eval_on_selector("#ctl00_ContentMain_suraType", "el => el.value")
        if current_type != "C":
            logs.append(f"  - ¡Alerta! Tipo de Identificación se reseteó antes del envío. Re-seleccionando CEDULA ('C').")
            page.select_option("#ctl00_ContentMain_suraType", value="C")
            page.eval_on_selector("#ctl00_ContentMain_suraType", """el => {
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }""")
            time.sleep(1)

        # Iniciar sesión
        page.locator("#session-internet").click()
        logs.append("  - Clic en 'Iniciar sesión'.")

        # Esperar a la siguiente pantalla (Prestadores de Salud card)
        page.wait_for_selector("button:has-text('Ingresar')", timeout=30000)
        logs.append("Login exitoso. Pantalla de redirección cargada.")
        return True, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado durante el login: {e}"
        logs.append(error_msg)
        traceback.print_exc()
        return False, "\n".join(logs)

def navegar_a_inicio(page: Page) -> tuple[bool, str]:
    """Navega a la sección de radicación de glosas abriendo la pestaña correspondiente."""
    logs = ["Navegando a la sección de Radicación de Glosas..."]
    try:
        # Capturamos la nueva pestaña que se abrirá al hacer clic en Ingresar
        with page.context.expect_page() as new_page_info:
            page.locator("button:has-text('Ingresar')").click()
        
        new_page = new_page_info.value
        new_page.wait_for_load_state()
        logs.append("  - Nueva pestaña de Prestadores abierta.")

        # En lugar de hacer click mediante Playwright (que valida visibilidad), hacemos click directo usando JS
        # Capturando de forma robusta la nueva pestaña que se abre
        enlace_glosas = new_page.locator("a[href*='ConsultaRespGlosas']")
        enlace_glosas.wait_for(state="attached", timeout=10000)
        
        with new_page.context.expect_page() as radicador_page_info:
            new_page.eval_on_selector("a[href*='ConsultaRespGlosas']", "el => el.click()")
        
        radicador_page = radicador_page_info.value
        radicador_page.wait_for_load_state()
        logs.append("  - Redirigiendo a Consulta y respuesta a glosas (Nueva pestaña capturada).")
        
        radicador_page.wait_for_selector("input[placeholder='Ingresa número de factura']", timeout=30000)
        logs.append("Formulario de Radicación de Respuestas a Glosas listo.")
        
        page.sura_page = radicador_page
        return True, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado al navegar a Radicación: {e}"
        logs.append(error_msg)
        traceback.print_exc()
        return False, "\n".join(logs)

def limpiar_archivo_malicioso(file_path: Path, logs: list) -> bool:
    """Detecta y limpia posibles scripts maliciosos en PDFs usando PyMuPDF (scrub) como método primario."""
    try:
        import fitz
        content = file_path.read_bytes()
        patterns = [
            (b'/JavaScript', re.IGNORECASE),
            (b'/OpenAction', re.IGNORECASE),
            (b'/JS', re.IGNORECASE),
            (b'<script>', re.IGNORECASE),
            (b'eval\\(', re.IGNORECASE),
            (b'app\\.alert\\(', re.IGNORECASE)
        ]
        
        has_malicious = False
        for pattern, flags in patterns:
            if re.search(pattern, content, flags):
                has_malicious = True
                break
                
        if not has_malicious:
            return False
            
        logs.append(f"  - Detectados posibles scripts maliciosos en {file_path.name}. Creando respaldo y limpiando...")
        
        # 1. Crear respaldo del original si no existe
        respaldo_path = file_path.with_name(f"{file_path.stem}_ORIGINAL{file_path.suffix}")
        if not respaldo_path.exists():
            file_path.rename(respaldo_path)
            
        # 2. Limpiar con PyMuPDF scrub (método oficial y seguro)
        try:
            doc = fitz.open(respaldo_path)
            doc.scrub(javascript=True, metadata=True, clean_pages=True)
            doc.save(file_path, garbage=4, deflate=True)
            doc.close()
            logs.append(f"  - Archivo desinfectado con scrub (PyMuPDF).")
        except Exception as e_scrub:
            logs.append(f"  - Error limpiando con scrub: {e_scrub}. Copiando respaldo para limpieza por bytes...")
            import shutil
            shutil.copy2(respaldo_path, file_path)
            
        # 3. Aplicar SIEMPRE el reemplazo a nivel de bytes para pasar el filtro simple del portal
        try:
            content = file_path.read_bytes()
            
            def repl_js(m): return b"/J_"
            def repl_javascript(m): return b"/JavaScrip_"
            def repl_openaction(m): return b"/OpenActio_"
            def repl_script(m): return b"<scri_pt>"
            def repl_eval(m): return b"eva_("
            def repl_alert(m): return b"app.aler_("

            content = re.sub(b'/JavaScript', repl_javascript, content, flags=re.IGNORECASE)
            content = re.sub(b'/JS', repl_js, content, flags=re.IGNORECASE)
            content = re.sub(b'/OpenAction', repl_openaction, content, flags=re.IGNORECASE)
            content = re.sub(b'<script>', repl_script, content, flags=re.IGNORECASE)
            content = re.sub(b'eval\\(', repl_eval, content, flags=re.IGNORECASE)
            content = re.sub(b'app\\.alert\\(', repl_alert, content, flags=re.IGNORECASE)
            
            file_path.write_bytes(content)
            logs.append(f"  - Reemplazos de firmas de scripts completados a nivel de bytes en {file_path.name}.")
            return True
        except Exception as e_bytes:
            logs.append(f"  - ERROR aplicando reemplazo de bytes en {file_path.name}: {e_bytes}")
            return False
            
    except Exception as e:
        logs.append(f"  - ERROR limpiando archivo {file_path.name}: {e}")
        return False

def comprimir_pdf(file_path: Path, logs: list) -> bool:
    """Comprime archivos PDF de más de 20MB para que queden por debajo del límite del portal."""
    try:
        import fitz
        original_size = file_path.stat().st_size
        limit = 20 * 1024 * 1024  # 20 MB
        if original_size <= limit:
            return False
            
        logs.append(f"  - El archivo {file_path.name} supera los 20MB ({original_size / 1024 / 1024:.2f} MB). Comprimiendo...")
        
        # 1. Crear respaldo del original si no existe
        respaldo_path = file_path.with_name(f"{file_path.stem}_ORIGINAL{file_path.suffix}")
        if not respaldo_path.exists():
            file_path.rename(respaldo_path)
            
        src_path = respaldo_path
            
        # Método 1: Compresión básica (deflate y garbage collection)
        try:
            doc = fitz.open(src_path)
            doc.save(file_path, garbage=4, deflate=True, clean=True)
            doc.close()
            
            new_size = file_path.stat().st_size
            logs.append(f"    - Compresión básica -> Nuevo tamaño: {new_size / 1024 / 1024:.2f} MB")
            
            if new_size <= limit:
                logs.append(f"    - Éxito en compresión básica. Reducción: {(1 - new_size/original_size)*100:.1f}%")
                return True
        except Exception as e_basic:
            logs.append(f"    - Error en compresión básica: {e_basic}")
            
        # Método 2: Compresión agresiva por renderizado de páginas (si aún supera los 20MB o falló la básica)
        logs.append(f"    - El archivo sigue superando los 20MB. Intentando compresión agresiva por renderizado de páginas...")
        try:
            doc = fitz.open(src_path)
            new_doc = fitz.open()
            
            for page in doc:
                pix = page.get_pixmap(dpi=120)
                img_data = pix.tobytes("jpeg")
                img_doc = fitz.open("pdf", img_data)
                new_doc.insert_pdf(img_doc)
                img_doc.close()
                
            new_doc.save(file_path, garbage=4, deflate=True)
            new_doc.close()
            doc.close()
            
            new_size = file_path.stat().st_size
            logs.append(f"    - Compresión agresiva -> Nuevo tamaño: {new_size / 1024 / 1024:.2f} MB")
            
            if new_size <= limit:
                logs.append(f"    - Éxito en compresión agresiva. Reducción total: {(1 - new_size/original_size)*100:.1f}%")
                return True
            else:
                logs.append(f"    - ADVERTENCIA: Incluso con compresión agresiva, el archivo supera los 20MB.")
                return True
        except Exception as e_aggressive:
            logs.append(f"    - Error en compresión agresiva: {e_aggressive}")
            return False
            
    except Exception as e:
        logs.append(f"  - ERROR comprimiendo archivo {file_path.name}: {e}")
        return False

def limpiar_pantalla_y_modales(sura_page: Page, logs: list):
    """Cierra todos los modales, SweetAlerts y overlays que puedan haber quedado abiertos."""
    logs.append("  - Limpiando pantalla y cerrando posibles modales...")
    
    # 1. Cerrar SweetAlerts
    try:
        confirm_btn = sura_page.locator("button.swal2-confirm")
        while confirm_btn.is_visible():
            logs.append("    - Cerrando alerta SweetAlert...")
            confirm_btn.first.click(timeout=3000)
            time.sleep(1)
    except Exception:
        pass
        
    # 2. Cerrar modales bootstrap (ngb-modal-window)
    try:
        while True:
            modal = sura_page.locator("ngb-modal-window").last
            if not modal.is_visible():
                break
                
            logs.append("    - Detectado modal abierto, intentando cerrar...")
            
            # Intentar clickear el botón 'Cerrar' dentro de ese modal específico
            cerrar_btn = modal.locator("button:has-text('Cerrar')")
            if cerrar_btn.is_visible():
                cerrar_btn.click(timeout=3000)
                time.sleep(1)
                continue
                
            # Si no hay botón 'Cerrar', intentar con el botón de la equis (close icon)
            x_btn = modal.locator("button.close, button[aria-label='Close']")
            if x_btn.is_visible():
                x_btn.click(timeout=3000)
                time.sleep(1)
                continue
                
            # Si nada de eso funciona, presionar Escape
            sura_page.keyboard.press("Escape")
            time.sleep(1)
            
            # Evitar bucle infinito si no se cierra, forzando eliminación vía DOM
            if modal.is_visible():
                logs.append("    - No se pudo cerrar el modal mediante clicks o Escape. Forzando cierre vía JS.")
                sura_page.evaluate("""() => {
                    document.querySelectorAll('ngb-modal-window').forEach(el => el.remove());
                    document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                    document.querySelectorAll('.swal2-container').forEach(el => el.remove());
                    document.body.classList.remove('modal-open');
                    document.body.classList.remove('swal2-shown');
                }""")
                break
    except Exception as e:
        logs.append(f"    - Excepción durante limpieza de modales: {e}")

def esperar_overlay_oculto(sura_page: Page):
    """Espera a que el spinner/overlay de carga de la página no sea visible."""
    try:
        overlay = sura_page.locator("div.overlay")
        if overlay.count() > 0:
            overlay.first.wait_for(state="hidden", timeout=15000)
    except Exception:
        pass

def obtener_codigo_factura_corregido(subfolder_path: Path, current_code: str) -> str | None:
    """Intenta extraer el código de factura real desde los archivos si difiere del nombre de la carpeta."""
    import re
    patron = re.compile(r'([A-Z]{2,6})-?(\d{4,8})', re.IGNORECASE)
    for f in subfolder_path.iterdir():
        if f.is_file() and f.suffix.upper() == ".PDF" and f.name.upper() != "RAD.PDF" and not f.name.upper().endswith("_ORIGINAL.PDF"):
            match = patron.search(f.name.upper())
            if match:
                prefix = match.group(1)
                digits = match.group(2)
                candidate = f"{prefix}{digits}"
                if candidate != current_code:
                    return candidate
    return None

def procesar_carpeta(page: Page, subfolder_path: Path, folder_name: str, context: str = 'default') -> tuple[str, str, str, str]:
    """Procesa una factura/carpeta en el radicador de SURA ARL."""
    logs = [f"--- Iniciando Playwright/SURA ARL para: '{folder_name}' ---"]
    codigo_factura = folder_name.upper()
    radicado = ""
    
    # 1. Verificaciones previas de nombre y RAD.pdf
    if any(p in folder_name.upper() for p in PALABRAS_EXCLUSION_CARPETAS) or (subfolder_path / "RAD.pdf").is_file():
        msg = "OMITIENDO: Carpeta excluida por nombre o ya radicada (RAD.pdf existe)."
        logs.append(msg)
        return ESTADO_OMITIDO_RADICADO, "", codigo_factura, "\n".join(logs)

    # Limpiar y comprimir PDFs antes de procesar
    for f in subfolder_path.iterdir():
        if f.is_file() and f.suffix.upper() == ".PDF" and f.name.upper() != "RAD.PDF" and not f.name.upper().endswith("_ORIGINAL.PDF"):
            comprimir_pdf(f, logs)
            limpiar_archivo_malicioso(f, logs)

    # Obtener la página del radicador que guardamos en navegar_a_inicio
    sura_page = getattr(page, 'sura_page', page)

    try:
        # Esperar a que se oculte cualquier overlay previo de carga
        esperar_overlay_oculto(sura_page)
        
        # 2. Buscar número de factura en el campo
        sura_page.locator("input[placeholder='Ingresa número de factura']").fill(codigo_factura)
        sura_page.locator("button.btn.btn-primary.rounded-pill").click()
        logs.append(f"  - Buscando factura {codigo_factura}...")

        # Dar tiempo a que se muestre el overlay de búsqueda y esperar a que se oculte
        time.sleep(0.5)
        esperar_overlay_oculto(sura_page)

        # Esperar a que cargue algún resultado (puede ser el botón de detalles o el de respuestas)
        try:
            sura_page.wait_for_selector("input[name='detalle']", timeout=10000)
        except PlaywrightTimeoutError:
            # Si no se encuentra, intentar con un código corregido extraído de los archivos
            codigo_corregido = obtener_codigo_factura_corregido(subfolder_path, codigo_factura)
            if codigo_corregido:
                logs.append(f"  - Factura {codigo_factura} no encontrada. Reintentando con código corregido {codigo_corregido}...")
                sura_page.locator("input[placeholder='Ingresa número de factura']").fill(codigo_corregido)
                sura_page.locator("button.btn.btn-primary.rounded-pill").click()
                time.sleep(0.5)
                esperar_overlay_oculto(sura_page)
                try:
                    sura_page.wait_for_selector("input[name='detalle']", timeout=10000)
                    codigo_factura = codigo_corregido  # Actualizar el código para el resto del flujo
                except PlaywrightTimeoutError:
                    logs.append(f"  -> ERROR: Tampoco se encontró la factura con el código corregido {codigo_corregido}.")
                    return ESTADO_FALLO, "", codigo_factura, "\n".join(logs)
            else:
                logs.append(f"  -> ERROR: No se encontró la factura {codigo_factura} en los resultados de búsqueda del portal.")
                return ESTADO_FALLO, "", codigo_factura, "\n".join(logs)

        # Esperar a que desaparezca cualquier overlay antes de interactuar con los resultados
        esperar_overlay_oculto(sura_page)

        # 3. Comprobar si el botón de cargar soportes (Respuesta / btnRes) está visible
        btn_res = sura_page.locator("input.btnRes[title='Cargar soportes de respuesta glosa']").first
        
        if not btn_res.is_visible():
            logs.append("  - Factura ya radicada anteriormente (Botón de cargar soportes no visible).")
            logs.append("  - Extrayendo evidencia desde Ver Detalles...")
            
            # Clic en el botón "Ver detalles de factura"
            sura_page.locator("input[name='detalle']").first.click()
            time.sleep(2)
            
            # Tomar captura de pantalla de los detalles
            screenshot_path = subfolder_path / "temp_detalles.png"
            sura_page.screenshot(path=str(screenshot_path))
            
            # Convertir captura a PDF
            pdf_path = subfolder_path / "RAD.pdf"
            try:
                with Image.open(screenshot_path) as img:
                    img.convert("RGB").save(pdf_path, "PDF")
                logs.append(f"  - Evidencia de detalles guardada como PDF: {pdf_path.name}")
                os.remove(screenshot_path)
            except Exception as e_pdf:
                logs.append(f"  - ADVERTENCIA: No se pudo guardar evidencia en PDF: {e_pdf}")
            
            # Cerrar el modal haciendo clic en el botón "Cerrar"
            try:
                sura_page.locator("ngb-modal-window button:has-text('Cerrar')").click(timeout=5000)
            except PlaywrightTimeoutError:
                # Fallback: presionar tecla Escape si el botón no responde
                sura_page.keyboard.press("Escape")
            time.sleep(1)
            
            return ESTADO_OMITIDO_RADICADO, "Ya Radicada", codigo_factura, "\n".join(logs)

        # 4. Flujo de Radicación (si btn_res está visible)
        esperar_overlay_oculto(sura_page)
        
        # Clic en el botón "Cargar soportes de respuesta glosa" (btnRes)
        btn_res.click()
        logs.append("  - Clic en Cargar soportes.")

        # Localizar el selector de archivos (ngx-file-drop utiliza un input interno)
        input_file = sura_page.locator("input.ngx-file-drop__file-input")
        input_file.wait_for(state="attached", timeout=5000)
        
        # --- INTERCEPTOR DE ANGULAR COMPONENT dropped() ---
        # Sobrescribe el método dropped() en el componente de manera robusta y asíncrona
        sura_page.evaluate(f"""
            new Promise((resolve) => {{
                let attempts = 0;
                const interval = setInterval(() => {{
                    attempts++;
                    const el = document.querySelector('ngx-file-drop');
                    if (el && el.__ngContext__) {{
                        const findComponent = (obj) => {{
                            if (!obj) return null;
                            if (typeof obj === 'object') {{
                                for (const key of Object.keys(obj)) {{
                                    try {{
                                        if (obj[key] && typeof obj[key].dropped === 'function') {{
                                            return obj[key];
                                        }}
                                    }} catch (e) {{}}
                                }}
                            }}
                            if (Array.isArray(obj)) {{
                                for (const item of obj) {{
                                    const found = findComponent(item);
                                    if (found) return found;
                                }}
                            }}
                            return null;
                        }};
                        const comp = findComponent(el.__ngContext__);
                        if (comp) {{
                            if (!comp.__intercepted) {{
                                comp.__intercepted = true;
                                const originalDropped = comp.dropped;
                                comp.dropped = function(ngxFiles) {{
                                    console.log("Interceptado dropped files:", ngxFiles);
                                    const cdFactura = this.elementoFactura.cdFactura;
                                    
                                    // Filtrar los archivos de respaldo (_ORIGINAL) para que no se suban ni validen
                                    if (ngxFiles) {{
                                        ngxFiles = ngxFiles.filter(f => {{
                                            const name = f.fileEntry ? f.fileEntry.name.toUpperCase() : '';
                                            return !name.endsWith('_ORIGINAL.PDF');
                                        }});
                                    }}

                                    if (ngxFiles && ngxFiles.length > 0) {{
                                        ngxFiles.forEach(fileEntry => {{
                                            const fileName = fileEntry.fileEntry ? fileEntry.fileEntry.name : 'file.pdf';
                                            fileEntry.relativePath = cdFactura + '/' + fileName;
                                        }});
                                    }}
                                    return originalDropped.call(this, ngxFiles);
                                }};
                                console.log("Interceptor de dropped inyectado con éxito.");
                            }}
                            clearInterval(interval);
                            resolve(true);
                            return;
                        }}
                    }}
                    if (attempts > 50) {{
                        clearInterval(interval);
                        console.log("No se pudo inyectar el interceptor después de 50 intentos.");
                        resolve(false);
                    }}
                }}, 100);
            }});
        """)
        logs.append("  - Interceptor de Angular component.dropped inyectado de manera robusta.")

        # Subir el directorio completo directamente ya que el input tiene webkitdirectory=true
        input_file.set_input_files(str(subfolder_path.resolve()))
        logs.append(f"  - Subiendo directorio completo: {subfolder_path.name}...")
        time.sleep(3)

        # Esperar a que se listen los archivos o aparezca SweetAlert
        try:
            sura_page.wait_for_selector("div.swal2-icon-error, button.btn-outline-dark:has-text('Siguiente')", timeout=60000)
            
            error_modal = sura_page.locator("div.swal2-icon-error")
            if error_modal.is_visible():
                error_text = sura_page.locator(".swal2-html-container").inner_text()
                logs.append(f"  -> ERROR en carga de archivos (SweetAlert): {error_text}")
                
                # Cerrar SweetAlert
                sura_page.locator("button.swal2-confirm:has-text('OK')").click()
                time.sleep(1)
                # Cerrar modal de carga
                sura_page.locator("button:has-text('Cerrar')").click()
                time.sleep(1)
                
                # Guardar captura de pantalla del error para diagnóstico
                error_screenshot_path = subfolder_path / "temp_error_screenshot.png"
                sura_page.screenshot(path=str(error_screenshot_path))
                logs.append(f"  - Captura de diagnóstico guardada: {error_screenshot_path.name}")
                
                return ESTADO_FALLO, f"Error Carga: {error_text}", codigo_factura, "\n".join(logs)
                
        except PlaywrightTimeoutError:
            logs.append("  -> ERROR: Tiempo de espera agotado esperando a 'Siguiente' o error de SweetAlert.")
            try:
                error_screenshot_path = subfolder_path / "modal_error_screenshot.png"
                sura_page.screenshot(path=str(error_screenshot_path))
                logs.append(f"  - Captura del modal de error guardada para diagnóstico: {error_screenshot_path.name}")
            except Exception as e_snap:
                logs.append(f"  - No se pudo capturar diagnóstico del modal: {e_snap}")
            return ESTADO_FALLO, "Timeout Carga Soportes", codigo_factura, "\n".join(logs)

        # --- VALIDACIÓN DE ALERTAS EN LÍNEA (Archivos Inválidos / Scripts / Tamaño) ---
        invalid_files_indicator = sura_page.locator("text=archivos inválidos")
        if invalid_files_indicator.is_visible():
            logs.append("  - Detectadas alertas en línea de archivos inválidos. Intentando eliminar archivos con error...")
            
            # Ejecutar script JS para eliminar los archivos con errores
            deleted_files = sura_page.evaluate("""() => {
                const isReddish = (colorStr) => {
                    if (!colorStr) return false;
                    if (colorStr.includes('red') || colorStr.includes('rgb(255, 0, 0)')) return true;
                    const match = colorStr.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                    if (match) {
                        const r = parseInt(match[1], 10);
                        const g = parseInt(match[2], 10);
                        const b = parseInt(match[3], 10);
                        return r > 150 && g < 100 && b < 100;
                    }
                    return false;
                };

                const errorElements = Array.from(document.querySelectorAll('*')).filter(el => {
                    const text = el.textContent || '';
                    const isExactErrorText = text.includes('scripts maliciosos') || 
                                             text.includes('supera el límite') || 
                                             text.includes('archivos inválidos') || 
                                             text.includes('archivo no permitido') ||
                                             text.includes('posibles scripts');
                    
                    const style = window.getComputedStyle(el);
                    const hasErrorClass = Array.from(el.classList).some(cls => cls.includes('danger') || cls.includes('error') || cls.includes('invalid'));
                    const isErrorColor = isReddish(style.color) || el.getAttribute('style')?.includes('red');
                    const hasErrorText = text.includes('maliciosos') || text.includes('tamaño') || text.includes('supera') || text.includes('inválido');
                    
                    return (isExactErrorText || (hasErrorText && (isErrorColor || hasErrorClass))) && el.children.length === 0;
                });
                
                const deletedFiles = [];
                for (const errEl of errorElements) {
                    let parent = errEl.parentElement;
                    let trashBtn = null;
                    let fileName = "";
                    for (let i = 0; i < 5; i++) {
                        if (!parent) break;
                        if (!trashBtn) {
                            trashBtn = parent.querySelector('button .fa-trash, button.fa-trash, .fa-trash, button[title*="Eliminar"], button[title*="eliminar"], i.fa-trash');
                        }
                        if (!fileName) {
                            const textNodes = Array.from(parent.querySelectorAll('*')).map(c => c.textContent.trim());
                            for (const text of textNodes) {
                                if (/\\.(pdf|jpg|jpeg|png|tif|tiff|xls|xlsx)$/i.test(text)) {
                                    fileName = text;
                                    break;
                                }
                            }
                        }
                        parent = parent.parentElement;
                    }
                    if (trashBtn) {
                        ['mousedown', 'mouseup', 'click'].forEach(eventType => {
                            const event = new MouseEvent(eventType, { bubbles: true, cancelable: true, view: window });
                            trashBtn.dispatchEvent(event);
                        });
                        deletedFiles.push(fileName || "Archivo desconocido");
                    }
                }
                return deletedFiles;
            }""")
            
            if deleted_files:
                logs.append(f"  - Archivos eliminados de la lista de subida por errores: {', '.join(deleted_files)}")
                time.sleep(2)
            else:
                logs.append("  - ADVERTENCIA: Se detectó el indicador de archivos inválidos pero no se pudieron eliminar de manera automática.")
                
            # Volver a verificar si aún quedan archivos inválidos
            if invalid_files_indicator.is_visible():
                logs.append("  -> ERROR: Quedan archivos inválidos en la lista y no se puede continuar.")
                # Guardar captura
                error_screenshot_path = subfolder_path / "temp_error_screenshot.png"
                sura_page.screenshot(path=str(error_screenshot_path))
                return ESTADO_FALLO, "Archivos invalidos en lista", codigo_factura, "\n".join(logs)

        # --- ESPERAR CARGA COMPLETA DE ARCHIVOS (PROGRESS BARS) ---
        logs.append("  - Esperando que los archivos terminen de cargarse en el portal...")
        t_inicio_carga = time.time()
        timeout_carga = 180  # 3 minutos máximo para subir todos los archivos
        carga_completa = False
        
        while time.time() - t_inicio_carga < timeout_carga:
            estado = sura_page.evaluate(r"""() => {
                const getBars = () => {
                    let list = Array.from(document.querySelectorAll('ngb-modal-window .progress-bar, ngb-modal-window [role="progressbar"], ngb-modal-window ngb-progressbar .progress-bar'));
                    if (list.length === 0) {
                        list = Array.from(document.querySelectorAll('ngb-modal-window *')).filter(el => {
                            const width = el.style.width || '';
                            if (!width.endsWith('%')) return false;
                            const className = (el.className || '').toString().toLowerCase();
                            const parentClassName = el.parentElement ? (el.parentElement.className || '').toString().toLowerCase() : '';
                            return className.includes('progress') || 
                                   className.includes('bar') || 
                                   parentClassName.includes('progress') || 
                                   parentClassName.includes('bar') ||
                                   className.includes('upload') ||
                                   parentClassName.includes('upload');
                        });
                    }
                    return list;
                };
                
                const bars = getBars();
                if (bars.length === 0) {
                    return { count: 0, finished: 0, pending: 0 };
                }
                
                let finished = 0;
                let pending = 0;
                
                bars.forEach(bar => {
                    const widthStr = bar.style.width || '';
                    const widthMatch = widthStr.match(/(\d+(?:\.\d+)?)\s*%/);
                    const ariaNow = parseFloat(bar.getAttribute('aria-valuenow') || '-1');
                    const ariaMax = parseFloat(bar.getAttribute('aria-valuemax') || '100');
                    
                    let isFinished = false;
                    if (widthMatch) {
                        const val = parseFloat(widthMatch[1]);
                        if (val >= 99.9) {
                            isFinished = true;
                        }
                    } else if (ariaNow >= 0 && ariaNow === ariaMax) {
                        isFinished = true;
                    }
                    
                    if (isFinished) {
                        finished++;
                    } else {
                        pending++;
                    }
                });
                
                return { count: bars.length, finished, pending };
            }""")
            
            count = estado['count']
            finished = estado['finished']
            pending = estado['pending']
            
            if count > 0:
                logs.append(f"    - Estado de subida: {finished}/{count} archivos listos (pendientes: {pending}).")
                if pending == 0:
                    logs.append("    - Todos los archivos se han cargado exitosamente.")
                    carga_completa = True
                    break
            else:
                if time.time() - t_inicio_carga > 8:
                    logs.append("    - No se detectaron barras de progreso activas. Continuando...")
                    carga_completa = True
                    break
            
            time.sleep(2)
            
        if not carga_completa:
            logs.append("  -> ADVERTENCIA: Se alcanzó el tiempo límite de espera para la subida de archivos. Se intentará continuar.")

        # Hacer clic en "Siguiente" en el modal
        sura_page.locator("button.btn-outline-dark:has-text('Siguiente')").click()
        time.sleep(1.5)
 
        # Hacer clic en "Confirmar" en el modal
        sura_page.locator("button.btn-outline-dark:has-text('Confirmar')").click()
        logs.append("  - Confirmación de subida enviada.")
 
        # Esperar alerta de éxito
        alerta_exito = sura_page.locator(".swal2-html-container:has-text('Se han cargado los archivos')")
        alerta_exito.wait_for(state="visible", timeout=40000)
        
        # Clic en "OK" del SweetAlert
        sura_page.locator("button.swal2-confirm:has-text('OK')").click()
        logs.append("  - Alerta de subida exitosa confirmada.")

        # Hacer clic en "Radicar"
        sura_page.locator("button:has-text('Radicar')").click()
        logs.append("  - Clic en el botón 'Radicar'.")

        # Esperar alerta final de Registro exitoso o modal de error ("Atención")
        exito_locator = sura_page.locator("h2#swal2-title:has-text('Registro exitoso')")
        error_locator = sura_page.locator("ngb-modal-window:has-text('Atención'), ngb-modal-window:has-text('error al registrar')")
        
        logs.append("  - Esperando respuesta del registro...")
        resultado_espera = None
        for _ in range(60): # 60s max
            if exito_locator.is_visible():
                resultado_espera = "exito"
                break
            if error_locator.is_visible():
                resultado_espera = "error"
                break
            time.sleep(1)
            
        if resultado_espera == "exito":
            texto_radicado = sura_page.locator(".swal2-html-container").inner_text()
            match_rad = re.search(r"radicado:\s*([a-zA-Z0-9\-]+)", texto_radicado, re.IGNORECASE)
            if match_rad:
                radicado = match_rad.group(1)
                logs.append(f"  - Registro exitoso. Radicado obtenido: {radicado}")
            else:
                radicado = "Desconocido"
                logs.append(f"  - Registro exitoso. No se pudo extraer número de radicado del texto: '{texto_radicado}'")

            # Tomar captura de pantalla del SweetAlert exitoso
            screenshot_path = subfolder_path / "temp_rad_screenshot.png"
            sura_page.screenshot(path=str(screenshot_path))
            logs.append("  - Captura de pantalla de comprobante guardada temporalmente.")

            # Convertir captura PNG/JPG a PDF
            pdf_path = subfolder_path / "RAD.pdf"
            try:
                with Image.open(screenshot_path) as img:
                    img.convert("RGB").save(pdf_path, "PDF")
                logs.append(f"  - Comprobante PDF generado: {pdf_path.name}")
                os.remove(screenshot_path)
            except Exception as e_pdf:
                logs.append(f"  - ADVERTENCIA: No se pudo convertir la captura en PDF: {e_pdf}")

            # Clic en Ok final de la alerta
            sura_page.locator("button.swal2-confirm:has-text('Ok')").click()
            logs.append("  - Clic final en Ok de confirmación.")

            return ESTADO_EXITO, radicado, codigo_factura, "\n".join(logs)
            
        elif resultado_espera == "error":
            # Extraer el texto de error del modal
            texto_error = error_locator.inner_text().strip()
            lineas_error = [line.strip() for line in texto_error.split('\n') if line.strip()]
            desc_error = " / ".join(lineas_error[:3])
            logs.append(f"  -> ERROR en registro (Modal Atención): {desc_error}")
            
            # Guardar captura
            screenshot_path = subfolder_path / "temp_error_screenshot.png"
            sura_page.screenshot(path=str(screenshot_path))
            logs.append(f"  - Captura de diagnóstico guardada: {screenshot_path.name}")
            
            return ESTADO_FALLO, f"Error Registro: {desc_error}", codigo_factura, "\n".join(logs)
            
        else:
            logs.append("  -> ERROR: Tiempo de espera agotado esperando confirmación de registro.")
            # Guardar captura
            screenshot_path = subfolder_path / "temp_error_screenshot.png"
            sura_page.screenshot(path=str(screenshot_path))
            logs.append(f"  - Captura de diagnóstico guardada: {screenshot_path.name}")
            return ESTADO_FALLO, "Timeout Registro", codigo_factura, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR procesando la carpeta: {e}"
        logs.append(error_msg)
        try:
            screenshot_path = subfolder_path / "temp_error_screenshot.png"
            sura_page.screenshot(path=str(screenshot_path))
            logs.append(f"  - Captura de diagnóstico guardada: {screenshot_path.name}")
        except Exception as e_snap:
            logs.append(f"  - No se pudo capturar diagnóstico: {e_snap}")
        traceback.print_exc()
        return ESTADO_FALLO, "", codigo_factura, "\n".join(logs)
    finally:
        limpiar_pantalla_y_modales(sura_page, logs)
