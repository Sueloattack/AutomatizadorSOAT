import os
import re
import traceback
from playwright.sync_api import Page, FrameLocator, expect, TimeoutError as PlaywrightTimeoutError
from Configuracion.constantes import MUNDIAL_ESCOLAR_URL
from Core.api_gema import query_api_gema

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
        logs.append("  - [Cookies] La notificación de cookies no apareció o ya fue aceptada.")
    except Exception as e:
        logs.append(f"  - [Cookies] ERROR inesperado: {e}")
    logs.append("Limpieza de pop-ups principales finalizada.")
    return True, "\n".join(logs)

def clear_iframe_popups(page: Page, frame: FrameLocator) -> tuple[bool, str]:
    """
    Detecta y cierra el modal '#infoModal' dentro del iframe (versión con 'page' como argumento).
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
            page.keyboard.press('Escape')
            page.wait_for_timeout(1000)
            expect(modal_locator).to_be_hidden(timeout=5000)
            logs.append("      -> Éxito: Modal cerrado con 'Escape'.")
            return True, "\n".join(logs)
    except PlaywrightTimeoutError:
        logs.append("    - El modal '#infoModal' no apareció (lo cual es normal).")
        return True, "\n".join(logs)
    except Exception as e:
        error_msg = f"    - ERROR FATAL al manejar el pop-up: {e}"
        page.screenshot(path="error_fatal_popup_iframe.png")
        logs.append(error_msg); traceback.print_exc()
        return False, "\n".join(logs)

def navegar_a_inicio(page: Page) -> tuple[bool, str, FrameLocator | None]:
    """
    Navega, entra al iframe, cierra el modal y LUEGO verifica el formulario.
    """
    logs = ["Navegando al formulario 'Pre-Respuesta de Glosa'..."]
    try:
        clear_main_page_popups(page)
        sub_item = page.locator("a:has-text('Pre-Respuesta de Glosa')")
        try:
            logs.append("  - Intento 1: Clic directo.")
            sub_item.click(timeout=5000)
        except PlaywrightTimeoutError:
            logs.append("  - Intento 1 fallido, abriendo menú padre.")
            page.locator("a:has-text('Tareas Auditoria')").click()
            sub_item.click(timeout=5000)
        logs.append("  - Clic en 'Pre-Respuesta de Glosa' exitoso.")
        
        logs.append("  - Esperando a que el iframe inicie la carga del contenido correcto...")
        iframe_element = page.locator("#ifrContentFrame")
        expect(iframe_element).to_have_attribute('src', re.compile(r'PreRespuestaGlosa', re.IGNORECASE), timeout=15000)
        logs.append("  - Confirmado: El iframe está cargando 'PreRespuestaGlosa'.")
        
        iframe = page.frame_locator("#ifrContentFrame")
        
        popup_iframe_ok, popup_iframe_log = clear_iframe_popups(page, iframe) # Llamada corregida
        logs.append(popup_iframe_log)
        if not popup_iframe_ok:
            raise Exception("Fallo crítico al intentar cerrar el modal dentro del iframe.")
            
        logs.append("  - Verificando la visibilidad del formulario principal ('input#textSearch')...")
        expect(iframe.locator("input#textSearch")).to_be_visible(timeout=30000)
        logs.append("  - Verificación exitosa: El formulario está visible y listo para usar.")
        
        return True, "\n".join(logs), iframe
    except Exception as e:
        error_msg = f"ERROR al navegar al formulario: {e}"
        page.screenshot(path="error_navegacion_mundial.png")
        logs.append(error_msg); traceback.print_exc()
        return False, "\n".join(logs), None

def procesar_factura(page: Page, frame: FrameLocator, glosa: dict, carpeta_salida_path: str) -> tuple[bool, str]:
    """Busca una factura dentro del iframe y analiza el resultado."""
    factura_a_buscar = glosa['factura_completa']
    logs = [f"  -> Buscando factura '{factura_a_buscar}'..."]
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
            page.screenshot(path=screenshot_path)
            logs.append(f"    - Captura de pantalla guardada en: {screenshot_path}")
            return False, "\n".join(logs)
        else:
             raise Exception("Se recibió una respuesta inesperada de la plataforma.")
    except PlaywrightTimeoutError:
        logs.append("    - Resultado: FALLO. No se encontró ni tabla de resultados ni mensaje de error (Factura no encontrada).")
        screenshot_path = os.path.join(carpeta_salida_path, "FALLO_no_encontrada.png")
        page.screenshot(path=screenshot_path)
        logs.append(f"    - Captura de pantalla guardada en: {screenshot_path}")
        return False, "\n".join(logs)
    except Exception as e:
        error_msg = f"  -> ERROR CRÍTICO durante la búsqueda de la factura: {e}"
        logs.append(error_msg)
        screenshot_path = os.path.join(carpeta_salida_path, "ERROR_INESPERADO_busqueda.png")
        try:
            page.screenshot(path=screenshot_path)
        except Exception:
            pass
        return False, "\n".join(logs)
    
def analizar_glosas_pendientes(page: Page, frame: FrameLocator) -> tuple[bool, str]:
    """Analiza y reporta las glosas pendientes encontradas."""
    logs = ["    -> Analizando detalles de glosas pendientes..."]
    try:
        contador_glosas_locator = frame.locator("span#spnCantFac")
        expect(contador_glosas_locator).to_be_visible(timeout=15000)
        total_glosas_str = contador_glosas_locator.inner_text()
        total_glosas = int(total_glosas_str)
        if total_glosas == 0:
            logs.append("      - No se encontraron glosas pendientes. Proceso finalizado para esta factura.")
            return True, "\n".join(logs)
        logs.append(f"      - Se encontraron {total_glosas} glosa(s) pendiente(s).")
        filas_glosas = frame.locator("#bodyGlosa tr.TrTable").all()
        if len(filas_glosas) != total_glosas:
            logs.append(f"      - ADVERTENCIA: El contador ({total_glosas}) no coincide con las filas de la tabla ({len(filas_glosas)}).")
        for i, fila in enumerate(filas_glosas):
            try:
                rubro = fila.locator("td").nth(0).inner_text().strip()
                valor_glosado = fila.locator("td").nth(1).inner_text().strip()
                boton_pendiente = fila.locator("button:has-text('Pendiente')")
                if boton_pendiente.is_visible():
                    boton_id = boton_pendiente.get_attribute('id')
                    logs.append(f"      - Glosa #{i+1}: ID='{boton_id}', Rubro='{rubro}', Valor='{valor_glosado}' -> [PENDIENTE]")
                else:
                    logs.append(f"      - Glosa #{i+1}: Rubro='{rubro}', Valor='{valor_glosado}' -> [ESTADO DESCONOCIDO]")
            except Exception as e_fila:
                logs.append(f"      - Error al procesar la fila de glosa #{i+1}: {e_fila}")
        return True, "\n".join(logs)
    except PlaywrightTimeoutError:
        error_msg = "    -> ERROR: No se pudo encontrar el contador de glosas ('#spnCantFac')."
        logs.append(error_msg)
        page.screenshot(path="error_analisis_glosas.png")
        return False, "\n".join(logs)
    except Exception as e:
        error_msg = f"    -> ERROR CRÍTICO durante el análisis de glosas: {e}"
        logs.append(error_msg)
        page.screenshot(path="error_analisis_glosas.png")
        return False, "\n".join(logs)
    
def _determinar_lote_y_radicabilidad(items_api_completos: list) -> tuple[bool, str, list | None]:
    """
    Función interna con lógica de negocio actualizada para determinar si una glosa se puede radicar.
    - Estados RADICABLES: C1, C2, C3, CO, AI
    - Estados NO RADICABLES (INICIAN): NU
    - Estados de BLOQUEO: R..., AE
    """
    if not items_api_completos:
        return False, "No se encontró historial de ítems en glo_det.", None

    # El último evento en la línea de tiempo
    ultimo_evento = items_api_completos[-1]
    ultimo_estado = ultimo_evento['estatus1'].strip().upper()
    
    # REGLA 1: Si el último estado es una Ratificación (R), está bloqueada.
    if ultimo_estado.startswith('R'):
        return False, f"No radicable: Pendiente de respuesta interna (último estado es '{ultimo_estado}').", None
    
    # REGLA 2: Si está Aceptada por Aseguradora (AE), el proceso terminó.
    if ultimo_estado == 'AE':
        return False, f"No radicable: La glosa ya está en estado final 'AE'.", None

    # Identificar el estado del último lote que requiere nuestra acción.
    # El orden de búsqueda es importante para encontrar el lote correcto.
    # CO es el último posible, luego C3, C2, C1, AI
    ultimo_lote_estado = None
    estados_que_podemos_contestar = ['CO', 'C3', 'C2', 'C1', 'AI'] 
    
    # Agrupamos los estados por cada fecha para entender los "eventos"
    estados_en_historial = {item['estatus1'].strip().upper() for item in items_api_completos}
    
    for estado_posible in estados_que_podemos_contestar:
        if estado_posible in estados_en_historial:
             # Este es el grupo más reciente que podemos/debemos contestar
             ultimo_lote_estado = estado_posible
             break

    if not ultimo_lote_estado:
         return False, "No se encontró un lote de ítems válido para procesar.", None
    
    # Si el último lote válido es NU, es una glosa nueva. Aún no se puede radicar respuesta.
    # El proceso debería ser: contestar internamente para que pase a C1.
    if ultimo_lote_estado == 'NU':
        return False, "No radicable: La glosa es nueva (NU) y requiere una primera respuesta interna.", None
    
    # Si llegamos aquí, encontramos un lote C..., CO o AI que podemos radicar.
    # Filtramos los ítems que pertenecen a ese lote
    lote_a_radicar = [item for item in items_api_completos if item['estatus1'].strip().upper() == ultimo_lote_estado]
    
    motivo = f"Radicable. Se procesará el lote de ítems con estado '{ultimo_lote_estado}'."
    return True, motivo, lote_a_radicar


# --- REEMPLAZA ESTA FUNCIÓN PRINCIPAL DE DIAGNÓSTICO ---
def diagnosticar_factura_desde_gema(glosa_info: dict) -> tuple[bool, str, list | None]:
    """
    Realiza el análisis de datos de una factura contra Gema.
    - Corrige el tipo de dato de la factura en la consulta SQL.
    - Añade logging detallado del lote a radicar.
    """
    prefijo = glosa_info['prefijo'].strip()
    factura = glosa_info['factura'].strip() # Mantenemos la factura como string
    logs = [f"--- Diagnóstico para {prefijo}{factura} ---"]
    
    try:
        # 1. Obtener gl_docn más reciente de 'glo_cab'
        # CORRECCIÓN: Volvemos a poner comillas en la factura, ya que fc_docn es de tipo Character
        sql_gl_docn = f"gl_docn, gl_fecha FROM [gema10.d/salud/datos/glo_cab] WHERE fc_serie = '{prefijo}' AND fc_docn = {factura} ORDER BY gl_fecha DESC"
        resultados_cab = query_api_gema(sql_gl_docn)
        
        if not resultados_cab:
            return False, "\n".join(logs + ["  - Resultado: FALLO. La factura no existe en glo_cab."]), None
        
        gl_docn_maestro = resultados_cab[0]['gl_docn']
        logs.append(f"  - gl_docn maestro encontrado: {gl_docn_maestro} (fecha: {resultados_cab[0].get('gl_fecha', 'N/A')})")

        # 2. Obtener todo el historial de 'glo_det'
        sql_gl_det = f"codigo, vr_glosa, motivo_res, estatus1, fecha_gl FROM [gema10.d/salud/datos/glo_det] WHERE gl_docn = {gl_docn_maestro} ORDER BY fecha_gl ASC, estatus1 ASC"
        items_api_completos = query_api_gema(sql_gl_det)
        logs.append(f"  - Se encontraron {len(items_api_completos)} eventos en el historial de la glosa.")

        # 3. Determinar si es radicable y qué lote usar, con la lógica actualizada
        es_radicable, motivo, lote_a_radicar = _determinar_lote_y_radicabilidad(items_api_completos)
        logs.append(f"  - Resultado del análisis: {motivo}")

        # Sección de LOGGING DETALLADO (como la pediste)
        if es_radicable and lote_a_radicar:
            logs.append("  - Detalles del lote a procesar:")
            total_lote = 0.0
            for i, item in enumerate(lote_a_radicar):
                valor = item.get('vr_glosa', 0.0)
                # Manejo de valor por si no es numérico
                try:
                    total_lote += float(valor)
                    valor_formateado = f"${float(valor):,.2f}"
                except (ValueError, TypeError):
                    valor_formateado = str(valor)

                logs.append(
                    f"    - Ítem {i+1}: "
                    f"Estado='{item.get('estatus1', 'N/A')}', "
                    f"Valor={valor_formateado}, "
                    f"Respuesta='{str(item.get('motivo_res', 'Sin respuesta'))[:50]}...'"
                )
            logs.append(f"    ----------------------------------")
            try:
                logs.append(f"    - Valor total del lote: ${total_lote:,.2f}")
            except (ValueError, TypeError):
                 logs.append(f"    - Valor total del lote: No se pudo calcular.")

        return es_radicable, "\n".join(logs), lote_a_radicar

    except Exception as e:
        logs.append(f"  - ERROR CRÍTICO durante el diagnóstico: {e}")
        return False, "\n".join(logs), None