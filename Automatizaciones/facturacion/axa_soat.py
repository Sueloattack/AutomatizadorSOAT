# AutomatizadorSOAT/Automatizaciones/facturacion/axa_soat.py (Versión con manejo de múltiples pop-ups de éxito)

import re
import json
import traceback
from pathlib import Path
from datetime import datetime
from playwright.sync_api import Page, expect, TimeoutError as PlaywrightTimeoutError

try:
    from Configuracion.constantes import *
    from Core.utilidades import encontrar_documentos_facturacion_axa
except ImportError as e:
    raise ImportError(f"ERROR CRITICO: Importaciones fallaron: {e}")

ESTADO_EXITO, ESTADO_FALLO, ESTADO_OMITIDO_RADICADO = "EXITO", "FALLO", "OMITIDO_RADICADO"

from ..glosas.axa_soat import login, asegurar_extension_pdf_minuscula

def navegar_a_inicio(page: Page) -> tuple[bool, str]:
    return True, "Navegación a inicio no es necesaria para AXA."

def handle_optional_popup(page: Page, timeout_ms: int = 5000) -> str:
    popup_selector = "div.justify-center.items-center.text-center > button:has-text('Aceptar')"
    try:
        page.locator(popup_selector).click(timeout=timeout_ms)
        return "  - Pop-up de notificación manejado."
    except PlaywrightTimeoutError: return "  - Pop-up de notificación no apareció."
    except Exception: return "  - Pop-up no procesado."

# --- Las funciones `llenar_formulario` y `subir_archivos` están correctas y no cambian ---
def llenar_formulario(page: Page, codigo_factura: str, cuv: str) -> tuple[bool, str]:
    logs = ["Llenando formulario de facturación..."]; 
    try:
        page.locator(AXASOAT_SELECTOR_NIT_RAMO).fill(AXASOAT_NIT_RAMO_FORM)
        page.locator(AXASOAT_SELECTOR_TIPO_CUENTA).select_option(label=AXASOAT_TIPO_CUENTA_FORM_FACTURACION)
        logs.append(handle_optional_popup(page))
        today_str = datetime.now().strftime("%Y-%m-%d"); page.locator(AXASOAT_SELECTOR_FECHA_ATENCION).fill(today_str)
        page.locator(AXASOAT_SELECTOR_NUMERO_FACTURA).fill(codigo_factura); logs.append(f"  - Factura: {codigo_factura}")
        logs.append(handle_optional_popup(page))
        checkbox_rips = page.locator(AXASOAT_SELECTOR_CHECKBOX_RIPS)
        if not checkbox_rips.is_checked(): checkbox_rips.check(); logs.append("  - Checkbox RIPS activado.")
        page.locator(AXASOAT_SELECTOR_CUV_INPUT).fill(cuv); logs.append("  - CUV ingresado.")
        page.locator(AXASOAT_SELECTOR_CORREO).fill(AXASOAT_CORREO_FACTURACION)
        page.locator(AXASOAT_SELECTOR_USUARIO_REGISTRA).fill(AXASOAT_USUARIO_REGISTRA_FACTURACION)
        logs.append("Formulario llenado con éxito."); return True, "\n".join(logs)
    except Exception as e: page.screenshot(path="error_formulario_axa.png"); logs.append(f"ERROR: {e}"); traceback.print_exc(); return False, "\n".join(logs)

def subir_archivos_facturacion(page: Page, paths_documentos: dict[str, Path]) -> tuple[bool, str]:
    logs = ["Subiendo archivos requeridos..."];
    try:
        MAPEO_SELECTORES = {
            "factura": AXASOAT_SELECTOR_INPUT_FACTURA_FILE, "furips": AXASOAT_SELECTOR_INPUT_FURIPS_FILE,
            "hc": AXASOAT_SELECTOR_INPUT_HC_FILE, "rips": AXASOAT_SELECTOR_INPUT_RIPS_JSON,
            "fev": AXASOAT_SELECTOR_INPUT_FEV_XML
        }
        for doc_tipo, path in paths_documentos.items():
            logs.append(handle_optional_popup(page, 2000))
            selector_directo = MAPEO_SELECTORES.get(doc_tipo);
            if not selector_directo: return False, f"ERROR: Selector para '{doc_tipo}' no mapeado."
            logs.append(f"  -> Subiendo {doc_tipo.upper()}: {path.name}...")
            page.locator(selector_directo).set_input_files(path)
            filename_locator = page.get_by_text(path.name, exact=True)
            expect(filename_locator).to_be_visible(timeout=120000)
            icono_papelera = filename_locator.locator("xpath=./ancestor::div[1]").locator("img[alt='img-response']")
            expect(icono_papelera).to_be_visible(timeout=5000)
            logs.append(f"  -> {doc_tipo.upper()} subido y confirmado OK.")
        return True, "\n".join(logs)
    except Exception as e: page.screenshot(path="error_subida_archivos_axa.png"); logs.append(f"ERROR: {e}"); traceback.print_exc(); return False, "\n".join(logs)

# <<< FUNCIÓN MODIFICADA PARA MANEJAR AMBOS POP-UPS DE ÉXITO >>>
def enviar_y_finalizar_radicado(page: Page) -> tuple[str | None, str]:
    """
    Envía el formulario y maneja los diferentes pop-ups de éxito para extraer el radicado.
    """
    logs = ["  Finalizando el proceso de radicación..."]
    radicado_extraido = None
    try:
        # 1. Manejar modal intermedio
        logs.append(handle_optional_popup(page))
        
        # 2. Clic en el botón "Enviar" final
        page.locator(AXASOAT_SELECTOR_BOTON_ENVIAR).click()
        logs.append("  -> Clic en 'Enviar'.")
        
        # 3. Esperar CUALQUIERA de los dos posibles pop-ups de éxito
        selector_exito_glosas = "p:has-text('reclamacion registrada correctamente')"
        selector_exito_facturacion = "p:has-text('Proceso exitoso')"
        
        logs.append("  -> Esperando modal de confirmación final...")
        
        # page.locator(A).or_(page.locator(B)) crea un nuevo locator que encuentra A o B
        popup_final = page.locator(selector_exito_glosas).or_(page.locator(selector_exito_facturacion))
        expect(popup_final).to_be_visible(timeout=60000)
        logs.append("  -> Modal de confirmación final detectado.")
        
        # 4. Extraer el radicado con una expresión regular universal
        texto_popup = popup_final.inner_text()
        # Este regex busca un guión y luego captura todos los dígitos que le siguen.
        match = re.search(r"-\s*(\d+)", texto_popup)
        if match:
            radicado_extraido = match.group(1)
            logs.append(f"  -> ¡ÉXITO! Radicado extraído: {radicado_extraido}")
        else:
            logs.append(f"  -> ADVERTENCIA: No se pudo extraer el radicado del texto: '{texto_popup}'")

        # 5. Cerrar el modal final (usando el mismo botón genérico 'Aceptar')
        page.locator("button:has-text('Aceptar')").click()
        expect(page.locator(AXASOAT_SELECTOR_FORMULARIO_VERIFY)).to_be_enabled(timeout=20000)
        logs.append("  -> Modal final cerrado. Formulario listo para la siguiente.")
        
        return radicado_extraido, "\n".join(logs)
    except Exception as e:
        page.screenshot(path="error_finalizacion_axa.png"); logs.append(f"ERROR en finalización: {e}"); traceback.print_exc()
        return None, "\n".join(logs)


# --- (El orquestador no cambia, ahora llama a la función corregida) ---
def procesar_carpeta(page: Page, subfolder_path: Path, subfolder_name: str) -> tuple[str, str | None, str | None, str]:
    # (El código aquí dentro es correcto y no necesita cambios)
    logs = [f"--- Iniciando AXA FACTURACIÓN | Carpeta: '{subfolder_name}' ---"]; radicado, codigo_factura = None, None
    try:
        if any(f.name.lower().endswith("-recibido.pdf") for f in subfolder_path.iterdir()):
            return ESTADO_OMITIDO_RADICADO, None, None, "\n".join(logs + ["OMITIENDO: Ya existe radicado."])
        codigo_factura, cuv, archivos_a_subir, docs_log = encontrar_documentos_facturacion_axa(subfolder_path, subfolder_name); logs.append(docs_log)
        if not all([codigo_factura, cuv, archivos_a_subir]): return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
        for tipo, path in archivos_a_subir.items():
            if path.suffix.lower() == ".pdf": path_final, rename_log = asegurar_extension_pdf_minuscula(path); archivos_a_subir[tipo] = path_final; logs.append(rename_log)
        form_ok, form_log = llenar_formulario(page, codigo_factura, cuv); logs.append(form_log)
        if not form_ok: return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
        logs.append(handle_optional_popup(page, 3000))
        upload_ok, upload_log = subir_archivos_facturacion(page, archivos_a_subir); logs.append(upload_log)
        if not upload_ok: return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
        radicado, final_log = enviar_y_finalizar_radicado(page); logs.append(final_log)
        if not radicado: return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
        return ESTADO_EXITO, radicado, codigo_factura, "\n".join(logs)
    except Exception as e:
        logs.append(f"ERROR CRÍTICO: {e}"); traceback.print_exc()
        return ESTADO_FALLO, radicado, codigo_factura, "\n".join(logs)