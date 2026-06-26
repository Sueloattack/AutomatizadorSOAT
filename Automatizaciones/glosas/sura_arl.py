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

    # Obtener la página del radicador que guardamos en navegar_a_inicio
    sura_page = getattr(page, 'sura_page', page)

    try:
        # 2. Buscar número de factura en el campo
        sura_page.locator("input[placeholder='Ingresa número de factura']").fill(codigo_factura)
        sura_page.locator("button.btn.btn-primary.rounded-pill").click()
        logs.append(f"  - Buscando factura {codigo_factura}...")

        # Esperar a que cargue algún resultado (puede ser el botón de detalles o el de respuestas)
        try:
            sura_page.wait_for_selector("input[name='detalle']", timeout=10000)
        except PlaywrightTimeoutError:
            logs.append("  -> ERROR: No se encontró la factura en los resultados de búsqueda del portal.")
            return ESTADO_FALLO, "", codigo_factura, "\n".join(logs)

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
        # Clic en el botón "Cargar soportes de respuesta glosa" (btnRes)
        btn_res.click()
        logs.append("  - Clic en Cargar soportes.")

        # Localizar el selector de archivos (ngx-file-drop utiliza un input interno)
        input_file = sura_page.locator("input.ngx-file-drop__file-input")
        input_file.wait_for(state="attached", timeout=5000)
        
        # --- INTERCEPTOR DE ANGULAR COMPONENT dropped() ---
        # Sobrescribe el método dropped() en el componente para forzar que relativePath pase la validación
        sura_page.evaluate(f"""
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
                if (comp && !comp.__intercepted) {{
                    comp.__intercepted = true;
                    const originalDropped = comp.dropped;
                    comp.dropped = function(ngxFiles) {{
                        console.log("Interceptado dropped files:", ngxFiles);
                        const cdFactura = this.elementoFactura.cdFactura;
                        if (ngxFiles && ngxFiles.length > 0) {{
                            ngxFiles.forEach(fileEntry => {{
                                const fileName = fileEntry.fileEntry ? fileEntry.fileEntry.name : 'file.pdf';
                                fileEntry.relativePath = cdFactura + '/' + fileName;
                            }});
                        }}
                        return originalDropped.call(this, ngxFiles);
                    }};
                    console.log("Interceptor de dropped inyectado.");
                }}
            }}
        """)
        logs.append("  - Interceptor de Angular component.dropped inyectado con éxito.")

        # Subir el directorio completo directamente ya que el input tiene webkitdirectory=true
        input_file.set_input_files(str(subfolder_path.resolve()))
        logs.append(f"  - Subiendo directorio completo: {subfolder_path.name}...")
        time.sleep(3)

        # Esperar a ver si aparece un SweetAlert de error o si el botón Siguiente está disponible
        try:
            sura_page.wait_for_selector("div.swal2-icon-error, button.btn-outline-dark:has-text('Siguiente')", timeout=15000)
            
            error_modal = sura_page.locator("div.swal2-icon-error")
            if error_modal.is_visible():
                error_text = sura_page.locator(".swal2-html-container").inner_text()
                logs.append(f"  -> ERROR en carga de archivos: {error_text}")
                
                # Cerrar SweetAlert
                sura_page.locator("button.swal2-confirm:has-text('OK')").click()
                time.sleep(1)
                # Cerrar modal de carga
                sura_page.locator("button:has-text('Cerrar')").click()
                time.sleep(1)
                
                # Guardar captura de pantalla del error para diagnóstico
                error_screenshot_path = Path("C:/Users/GLOSAS/.gemini/antigravity-ide/brain/db1e50eb-d9c0-4444-8e27-212acea691ea/temp_error_screenshot.png")
                sura_page.screenshot(path=str(error_screenshot_path))
                logs.append(f"  - Captura de diagnóstico guardada: {error_screenshot_path.name}")
                
                return ESTADO_FALLO, f"Error Carga: {error_text}", codigo_factura, "\n".join(logs)
                
            # Hacer clic en "Siguiente" en el modal
            sura_page.locator("button.btn-outline-dark:has-text('Siguiente')").click()
            time.sleep(1.5)
        except PlaywrightTimeoutError:
            logs.append("  -> ERROR: Tiempo de espera agotado esperando a 'Siguiente' o error de SweetAlert.")
            return ESTADO_FALLO, "Timeout Carga Soportes", codigo_factura, "\n".join(logs)

        # Hacer clic en "Confirmar" en el modal
        sura_page.locator("button.btn-outline-dark:has-text('Confirmar')").click()
        logs.append("  - Confirmación de subida enviada.")

        # Esperar alerta de éxito
        alerta_exito = sura_page.locator(".swal2-html-container:has-text('Se han cargado los archivos')")
        alerta_exito.wait_for(state="visible", timeout=20000)
        
        # Clic en "OK" del SweetAlert
        sura_page.locator("button.swal2-confirm:has-text('OK')").click()
        logs.append("  - Alerta de subida exitosa confirmada.")

        # Hacer clic en "Radicar"
        sura_page.locator("button:has-text('Radicar')").click()
        logs.append("  - Clic en el botón 'Radicar'.")

        # Esperar alerta final de Registro exitoso y extraer el radicado
        alerta_final = sura_page.locator("h2#swal2-title:has-text('Registro exitoso')")
        alerta_final.wait_for(state="visible", timeout=30000)
        
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

    except Exception as e:
        error_msg = f"ERROR procesando la carpeta: {e}"
        logs.append(error_msg)
        try:
            # Intentar guardar una captura del error para diagnóstico visual
            screenshot_path = subfolder_path / "temp_error_screenshot.png"
            sura_page.screenshot(path=str(screenshot_path))
            logs.append(f"  - Captura de diagnóstico guardada: {screenshot_path.name}")
        except Exception as e_snap:
            logs.append(f"  - No se pudo capturar diagnóstico: {e_snap}")
        traceback.print_exc()
        return ESTADO_FALLO, "", codigo_factura, "\n".join(logs)
