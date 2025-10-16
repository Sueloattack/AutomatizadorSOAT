import os
import re
import traceback
from playwright.sync_api import Page, FrameLocator, expect, TimeoutError as PlaywrightTimeoutError
from Configuracion.constantes import MUNDIAL_ESCOLAR_URL

def login(page: Page, usuario: str, contrasena: str) -> tuple[bool, str]:
    """Inicia sesión en la plataforma de Mundial usando constantes."""
    logs = [f"Iniciando login en Mundial Escolar para usuario: {usuario}..."]
    try:
        page.goto(MUNDIAL_ESCOLAR_URL, timeout=60000)
        logs.append(f"  Página cargada: {MUNDIAL_ESCOLAR_URL}")

        page.fill("input[name='user']", usuario)
        page.fill("input[name='pass']", contrasena)
        page.click("button[type='submit']")
        
        expect(page.locator("span.menu-text:has-text('Tareas Auditoria')")).to_be_visible(timeout=30000)
        logs.append("  Login exitoso.")
        return True, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado durante el login: {e}"
        page.screenshot(path="error_login_mundial.png")
        logs.append(error_msg); traceback.print_exc()
        return False, "\n".join(logs)

def clear_main_page_popups(page: Page) -> tuple[bool, str]:
    """Maneja pop-ups en la página principal, como las cookies."""
    logs = ["Iniciando limpieza de pop-ups en la página principal..."]
    try:
        cookie_button = page.locator("button#cookies__button:visible")
        logs.append("  - [Cookies] Buscando notificación (espera máxima 7 seg)...")
        cookie_button.wait_for(timeout=7000)
        cookie_button.click()
        logs.append("  - [Cookies] Notificación aceptada.")
    except PlaywrightTimeoutError:
        logs.append("  - [Cookies] La notificación no apareció o ya fue aceptada.")
    except Exception as e:
        logs.append(f"  - [Cookies] ERROR inesperado: {e}")
    logs.append("Limpieza de pop-ups principales finalizada.")
    return True, "\n".join(logs)

def navegar_a_inicio(page: Page) -> tuple[bool, str, FrameLocator | None]:
    """
    Versión definitiva: Navega, entra al iframe, cierra el modal y LUEGO verifica el formulario.
    """
    logs = ["Navegando al formulario 'Pre-Respuesta de Glosa'..."]
    try:
        clear_main_page_popups(page) # Limpia cookies, etc. de la página principal

        sub_item = page.locator("a:has-text('Pre-Respuesta de Glosa')")
        try:
            logs.append("  - Intento 1: Clic directo.")
            sub_item.click(timeout=5000)
        except PlaywrightTimeoutError:
            logs.append("  - Intento 1 fallido, abriendo menú padre.")
            page.locator("a:has-text('Tareas Auditoria')").click()
            sub_item.click(timeout=5000)
        logs.append("  - Clic en 'Pre-Respuesta de Glosa' exitoso.")
        
        # --- NUEVA SECUENCIA LÓGICA ---

        # 1. ESPERAR Y VERIFICAR que el iframe ha recibido la orden de carga.
        logs.append("  - Esperando a que el iframe inicie la carga del contenido correcto...")
        iframe_element = page.locator("#ifrContentFrame")
        expect(iframe_element).to_have_attribute('src', re.compile(r'PreRespuestaGlosa', re.IGNORECASE), timeout=15000)
        logs.append("  - Confirmado: El iframe está cargando 'PreRespuestaGlosa'.")
        
        # 2. OBTENER el FrameLocator. NO verificamos nada dentro aún.
        iframe = page.frame_locator("#ifrContentFrame")
        
        # 3. CERRAR EL MODAL PRIMERO. Le damos tiempo suficiente para que aparezca después de la carga inicial del iframe.
        #    Esta función ya es tolerante: si el modal no aparece, simplemente continúa.
        popup_iframe_ok, popup_iframe_log = clear_iframe_popups(iframe)
        logs.append(popup_iframe_log)
        if not popup_iframe_ok:
            raise Exception("Fallo crítico al intentar cerrar el modal dentro del iframe.")
            
        # 4. AHORA SÍ, con el modal ya cerrado, VERIFICAMOS que el formulario de fondo sea visible.
        logs.append("  - Verificando la visibilidad del formulario principal ('input[name=Factura]')...")
        expect(iframe.locator("input#textSearch")).to_be_visible(timeout=30000)
        logs.append("  - Verificación exitosa: El formulario está visible y listo para usar.")
        
        return True, "\n".join(logs), iframe

    except Exception as e:
        error_msg = f"ERROR al navegar al formulario: {e}"
        page.screenshot(path="error_navegacion_mundial.png")
        logs.append(error_msg); traceback.print_exc()
        return False, "\n".join(logs), None

    except Exception as e:
        error_msg = f"ERROR al navegar al formulario: {e}"
        page.screenshot(path="error_navegacion_mundial.png")
        logs.append(error_msg); traceback.print_exc()
        return False, "\n".join(logs), None


def clear_iframe_popups(frame: FrameLocator) -> tuple[bool, str]:
    """
    Detecta y cierra el modal '#infoModal' dentro del iframe con selectores corregidos.
    """
    logs = ["  - Iniciando limpieza de pop-ups DENTRO del iframe..."]
    
    try:
        modal_locator = frame.locator("div#infoModal")
        logs.append("    - [Modal] Buscando pop-up '#infoModal' (espera máxima 15 seg)...")
        modal_locator.wait_for(state="visible", timeout=15000)
        logs.append("    - ¡Modal '#infoModal' detectado! Intentando cerrar...")

        try:
            logs.append("      -> Intento: Clic en botón con 'data-dismiss=\"modal\"'.")
            close_button = modal_locator.locator("button[data-dismiss='modal']:visible").first
            close_button.click(timeout=5000)
            expect(modal_locator).to_be_hidden(timeout=5000)
            logs.append("      -> Éxito: Modal cerrado.")
            return True, "\n".join(logs)
        except Exception as e:
            logs.append(f"      -> Clic fallido, intentando con tecla 'Escape'. Razón: {e}")
            frame.page.keyboard.press('Escape')
            frame.page.wait_for_timeout(1000)
            expect(modal_locator).to_be_hidden(timeout=5000)
            logs.append("      -> Éxito: Modal cerrado con 'Escape'.")
            return True, "\n".join(logs)

    except PlaywrightTimeoutError:
        logs.append("    - El modal '#infoModal' no apareció (lo cual es normal).")
        return True, "\n".join(logs)
        
    except Exception as e:
        error_msg = f"    - ERROR FATAL al manejar el pop-up: {e}"
        frame.page.screenshot(path="error_fatal_popup_iframe.png")
        logs.append(error_msg); traceback.print_exc()
        return False, "\n".join(logs)
    
# --- NUEVA FUNCIÓN ---
def procesar_factura(page: Page, frame: FrameLocator, glosa: dict, carpeta_salida_path: str) -> tuple[bool, str]:
    """
    Busca una factura. Versión que recibe 'page' como argumento y corrige el AttributeError.
    """
    factura_a_buscar = glosa['factura_completa']
    logs = [f"  -> Buscando factura '{factura_a_buscar}'..."]
    
    # YA NO NECESITAMOS 'page = frame.page', porque ahora recibimos 'page' directamente.

    try:
        frame.locator('input#textSearch').clear()
        frame.locator('input#textSearch').fill(factura_a_buscar)
        frame.locator('button#btnBuscar').click()
        logs.append(f"  -> Búsqueda realizada. Esperando resultado...")

        tabla_resultados_locator = frame.locator("table td a[id^='td_']")
        mensaje_conciliacion_locator = frame.locator("div.alert-danger:has-text('en proceso de conciliación')")
        
        expect(
            tabla_resultados_locator.or_(mensaje_conciliacion_locator)
        ).to_be_visible(timeout=20000)
        logs.append("    - Respuesta de la plataforma recibida. Analizando...")

        if tabla_resultados_locator.is_visible():
            logs.append("    - Resultado: ÉXITO. Tabla de facturas encontrada.")
            responder_glosa_icon = tabla_resultados_locator
            
            if responder_glosa_icon.count() == 1:
                logs.append("    - Ícono de 'Responder Glosas' encontrado. Haciendo clic...")
                responder_glosa_icon.click()
                return True, "\n".join(logs)
            else:
                raise Exception(f"Se encontraron {responder_glosa_icon.count()} resultados para '{factura_a_buscar}'. Se esperaba 1.")

        elif mensaje_conciliacion_locator.is_visible():
            texto_error = mensaje_conciliacion_locator.inner_text().strip().replace('\n', ' ')
            logs.append(f"    - Resultado: FALLO. {texto_error}")
            screenshot_path = os.path.join(carpeta_salida_path, "FALLO_en_conciliacion.png")
            page.screenshot(path=screenshot_path) # Usamos 'page' para el screenshot
            logs.append(f"    - Captura de pantalla guardada en: {screenshot_path}")
            return False, "\n".join(logs)
        
        else:
             raise Exception("Se recibió una respuesta inesperada de la plataforma.")

    except PlaywrightTimeoutError:
        logs.append("    - Resultado: FALLO. No se encontró ni tabla de resultados ni mensaje de error (Factura no encontrada).")
        screenshot_path = os.path.join(carpeta_salida_path, "FALLO_no_encontrada.png")
        page.screenshot(path=screenshot_path) # Usamos 'page' para el screenshot
        logs.append(f"    - Captura de pantalla guardada en: {screenshot_path}")
        return False, "\n".join(logs)

    except Exception as e:
        error_msg = f"  -> ERROR CRÍTICO durante la búsqueda de la factura: {e}"
        logs.append(error_msg)
        screenshot_path = os.path.join(carpeta_salida_path, "ERROR_INESPERADO_busqueda.png")
        try:
            page.screenshot(path=screenshot_path) # Usamos 'page' para el screenshot
        except Exception:
            pass
        return False, "\n".join(logs)