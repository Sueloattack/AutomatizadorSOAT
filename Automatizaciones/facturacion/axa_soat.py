# AutomatizadorSOAT/Automatizaciones/facturacion/axa_soat.py

"""
Módulo de automatización para el proceso de FACTURACIÓN de AXA Colpatria SOAT.

Este módulo contiene la lógica específica para:
1.  Llenar el formulario de radicación de facturas por primera vez.
2.  Manejar modales, validaciones previas y RIPS.
3.  Subir los 6 archivos requeridos (Historia Clínica, Factura, Furips, RIPS JSON, FEV XML, CUV TXT).
4.  Enviar el formulario, extraer el número de radicado final y generar el comprobante PDF.

Reutiliza funciones comunes como `login` del módulo de Glosas de AXA.
"""

# --- Importaciones de Sistema y Librerías Externas ---
import re
import time
import traceback
from pathlib import Path
from PIL import Image
from playwright.sync_api import Page, expect, TimeoutError as PlaywrightTimeoutError

# --- Importaciones Internas del Proyecto ---
try:
    from Configuracion.constantes import *
    from Core.utilidades import encontrar_documentos_facturacion_axa, guardar_screenshot_de_error
except ImportError as e:
    raise ImportError(f"ERROR CRITICO: Importaciones fallaron: {e}")

# Reutilización de funciones comunes desde el módulo de glosas de AXA
from ..glosas.axa_soat import login, navegar_a_inicio, asegurar_extension_pdf_minuscula, asegurar_formulario_limpio

# --- Definición de Estados del Proceso ---
ESTADO_EXITO = "EXITO"
ESTADO_FALLO = "FALLO"
ESTADO_OMITIDO_RADICADO = "OMITIDO_RADICADO"

# ==============================================================================
# --- FUNCIONES DE INTERACCIÓN WEB ESPECIALIZADAS PARA FACTURACIÓN ---
# ==============================================================================

def llenar_formulario(page: Page, codigo_factura: str, cuv: str) -> tuple[bool, str]:
    """
    Rellena todos los campos del formulario de radicación de facturas por primera vez.
    """
    logs = ["Llenando formulario de facturación AXA..."]
    try:
        # 1. NIT Ramo SOAT Colpatria (8600021846)
        nit_loc = page.locator("input.input-number-nit, input[placeholder*='NIT ramo SOAT Colpatria']").first
        nit_loc.wait_for(state="visible", timeout=20000)
        nit_loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        nit_loc.press_sequentially(str(AXASOAT_NIT_RAMO_FORM), delay=30)
        nit_loc.dispatch_event("input")
        nit_loc.dispatch_event("change")
        nit_loc.evaluate("el => el.blur()")
        logs.append(f"  - NIT Ramo SOAT: {AXASOAT_NIT_RAMO_FORM}")

        # 2. N° Factura
        inv_loc = page.locator("input[name='invoiceNumber']").first
        inv_loc.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        inv_loc.press_sequentially(codigo_factura.upper(), delay=30)
        inv_loc.dispatch_event("input")
        inv_loc.dispatch_event("change")
        inv_loc.evaluate("el => el.blur()")
        logs.append(f"  - N° Factura: {codigo_factura.upper()}")

        # Manejo de modal informativo si la factura ya tuvo radicado previo o aviso
        for _ in range(12):
            page.wait_for_timeout(350)
            modal_loc = page.locator("div.modal-content, mok-modal").first
            modal_visible = False
            modal_txt = ""
            try:
                if modal_loc.is_visible():
                    modal_visible = True
                    modal_txt = modal_loc.inner_text()
            except Exception:
                pass

            if modal_visible and ("fue recibida" in modal_txt.lower() or "siguiente reclamaci" in modal_txt.lower() or "importante" in modal_txt.lower()):
                logs.append("  - AVISO: Mensaje informativo detectado. Cerrando modal...")
                try:
                    btn_modal = page.locator("div.modal-content button:has-text('ACEPTAR'), div.modal-content button:has-text('Aceptar'), mok-modal button:has-text('ACEPTAR'), mok-modal button:has-text('Aceptar')").last
                    if btn_modal.is_visible(timeout=3000):
                        btn_modal.click(force=True)
                except Exception:
                    pass
                page.wait_for_timeout(1000)
                break

        # Limpiar backdrops u overlays
        try:
            page.evaluate("""() => {
                document.querySelectorAll('mok-modal button, div.modal-content button').forEach(b => {
                    if (b.innerText && (b.innerText.includes('ACEPTAR') || b.innerText.includes('Aceptar'))) b.click();
                });
                document.querySelectorAll('div[class*="backdrop-blur"], div[class*="bg-[#00000050]"]').forEach(o => o.click());
            }""")
        except Exception:
            pass
        page.wait_for_timeout(500)

        # 3. Checkbox RIPS: debe estar marcado para facturación
        chk = page.locator("input[type='checkbox']").first
        if chk.count() > 0 and not chk.is_checked():
            try:
                chk.check(force=True)
                logs.append("  - Checkbox RIPS marcado.")
            except Exception:
                pass

        # 4. Usuario que registra: CLINICA ASOTRAUMA
        usr_nombre = "CLINICA ASOTRAUMA"
        usr_loc = page.locator("input[name='userRegister']").first
        usr_loc.wait_for(state="visible", timeout=10000)
        try:
            usr_loc.click(timeout=3000)
        except Exception:
            usr_loc.click(force=True)

        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        usr_loc.press_sequentially(usr_nombre, delay=30)
        usr_loc.dispatch_event("input")
        usr_loc.dispatch_event("change")
        usr_loc.evaluate("el => el.blur()")
        logs.append(f"  - Usuario que Registra: {usr_nombre}")
        page.wait_for_timeout(500)

        # 5. Tipo de cuenta: 'Factura presentada por primera vez'
        tipo_cta_input = page.locator("input[data-analytics='input-select-accountType'], input[placeholder='Seleccione una opción']").first
        try:
            tipo_cta_input.click(timeout=5000)
        except Exception:
            tipo_cta_input.click(force=True)
        page.wait_for_timeout(500)

        opcion_locator = page.locator("text=/primera vez/i").last
        if opcion_locator.is_visible(timeout=3000):
            try:
                opcion_locator.click(timeout=3000)
            except Exception:
                opcion_locator.click(force=True)
            logs.append(f"  - Tipo de cuenta seleccionado: '{AXASOAT_TIPO_CUENTA_FORM_FACTURACION}'")
        else:
            page.locator(f"div:has-text('{AXASOAT_TIPO_CUENTA_FORM_FACTURACION}'), span:has-text('{AXASOAT_TIPO_CUENTA_FORM_FACTURACION}')").last.click(force=True)
            logs.append(f"  - Tipo de cuenta seleccionado vía texto: '{AXASOAT_TIPO_CUENTA_FORM_FACTURACION}'")

        page.wait_for_timeout(500)

        # 6. CUV en campo de texto
        cuv_txt = page.locator(AXASOAT_SELECTOR_CUV_INPUT).first
        if cuv_txt.count() > 0:
            cuv_txt.click(force=True)
            cuv_txt.fill(cuv)
            cuv_txt.dispatch_event("input")
            cuv_txt.dispatch_event("change")
            cuv_txt.evaluate("el => el.blur()")
            logs.append(f"  - CUV ingresado en campo de texto: {cuv[:30]}...")

        logs.append("Formulario llenado con éxito y sección de Soportes habilitada.")
        return True, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR inesperado al llenar el formulario de AXA Facturación: {e}"
        logs.append(error_msg); traceback.print_exc()
        log_screenshot = guardar_screenshot_de_error(page, "error_formulario_axa_facturacion")
        logs.append(log_screenshot)
        return False, "\n".join(logs)


def subir_archivos_facturacion(page: Page, paths_documentos: dict[str, Path]) -> tuple[bool, str]:
    """
    Sube los 6 archivos requeridos a sus respectivos inputs de archivo en la UI de AXA Facturación.
    """
    logs = ["Subiendo archivos requeridos de Facturación..."]
    try:
        MAPEO_SELECTORES = {
            "hc": AXASOAT_SELECTOR_INPUT_HC_FILE,
            "factura": AXASOAT_SELECTOR_INPUT_FACTURA_FILE,
            "furips": AXASOAT_SELECTOR_INPUT_FURIPS_FILE,
            "rips": AXASOAT_SELECTOR_INPUT_RIPS_JSON,
            "fev": AXASOAT_SELECTOR_INPUT_FEV_XML,
            "cuv_file": AXASOAT_SELECTOR_INPUT_CUV_FILE
        }

        for doc_tipo, path in paths_documentos.items():
            if not path or not path.exists():
                continue

            selector = MAPEO_SELECTORES.get(doc_tipo)
            if not selector:
                continue

            logs.append(f"  -> Subiendo {doc_tipo.upper()}: {path.name}...")
            inp_loc = page.locator(selector).first
            inp_loc.set_input_files(str(path))
            page.wait_for_timeout(1000)
            logs.append(f"  -> {doc_tipo.upper()} adjuntado correctamente.")

        page.wait_for_timeout(1500)
        return True, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR al subir archivos de AXA Facturación: {e}"
        logs.append(error_msg); traceback.print_exc()
        log_screenshot = guardar_screenshot_de_error(page, "error_subida_archivos_facturacion")
        logs.append(log_screenshot)
        return False, "\n".join(logs)


def enviar_y_finalizar_radicado(page: Page, subfolder_path: Path, codigo_factura: str) -> tuple[str | None, str]:
    """
    Sincroniza el estado de React Fiber, hace clic en 'Guardar información',
    espera el modal de confirmación con el checkmark azul y guarda el PDF del radicado.
    """
    logs = ["Finalizando el proceso de radicación..."]
    radicado_extraido = None
    response_radicado = []

    def on_response(res):
        if "reception" in res.url:
            try:
                txt = res.text()
                m = re.search(r"creada\s+con\s+[eé]xito\s+(\d+)", txt, re.IGNORECASE) or \
                    re.search(r"Ok.*?(\d{7,10})", txt, re.IGNORECASE)
                if m:
                    response_radicado.append(m.group(1))
            except Exception:
                pass

    page.on("response", on_response)

    try:
        # Sincronización precisa de React Fiber
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
                        if (idx === 6 && cur.queue) cur.queue.dispatch({});
                        if (idx === 8 && cur.queue) cur.queue.dispatch(true);
                        if (idx === 11 && cur.queue) cur.queue.dispatch({});
                        if (idx === 15 && cur.queue) cur.queue.dispatch(true);
                        if (idx === 16 && cur.queue) cur.queue.dispatch("N");
                        if (idx === 17 && cur.queue) {
                            cur.queue.dispatch(prev => {
                                const base = prev || {};
                                return {
                                    ...base,
                                    nit: "8600021846",
                                    invoiceNumber: String(data.invoice || ''),
                                    userRegister: "CLINICA ASOTRAUMA",
                                    accountType: "N"
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
        # Clic en 'Guardar información'
        boton_guardar = page.locator("button:has-text('Guardar información')").last
        boton_guardar.wait_for(state="visible", timeout=10000)
        boton_guardar.scroll_into_view_if_needed()
        boton_guardar.click()
        logs.append("  -> Clic en 'Guardar información'.")

        # Esperar a que el modal con el resultado aparezca
        logs.append("  -> Esperando procesamiento del envío...")
        for _ in range(60):
            page.wait_for_timeout(1000)
            txt_actual = ""
            try:
                txt_actual = page.locator("div.modal-content, mok-modal").last.inner_text()
            except Exception:
                pass
            if "enviando la información" not in txt_actual.lower() and ("creada con éxito" in txt_actual.lower() or "importante" in txt_actual.lower() or "exitoso" in txt_actual.lower() or response_radicado):
                break

        page.wait_for_timeout(2000)

        modal_text = ""
        try:
            # Recorrer todos los modales visibles y capturar el texto
            for m_elem in page.locator("div.modal-content, mok-modal").all():
                if m_elem.is_visible():
                    t = m_elem.inner_text()
                    if t:
                        modal_text += "\n" + t
        except Exception:
            pass

        if not modal_text.strip():
            try:
                modal_text = page.locator("body").inner_text()
            except Exception:
                pass

        if "Verifique los campos requeridos" in modal_text or "error al enviar" in modal_text.lower():
            logs.append(f"  -> ERROR en validación del formulario: {modal_text.strip()}")
            log_shot = guardar_screenshot_de_error(page, f"error_envio_{codigo_factura}")
            logs.append(log_shot)
            return None, "\n".join(logs)

        match = re.search(r"Reclamaci[oó]n\s+creada\s+con\s+[eé]xito\s+(\d+)", modal_text, re.IGNORECASE) or \
                re.search(r"creada\s+con\s+[eé]xito\s*[:#-]?\s*(\d+)", modal_text, re.IGNORECASE) or \
                re.search(r"(\d{7,10})", modal_text)

        if match:
            radicado_extraido = match.group(1)
        elif response_radicado:
            radicado_extraido = response_radicado[-1]

        if radicado_extraido:
            logs.append(f"  -> ¡ÉXITO! Radicado obtenido: {radicado_extraido}")
            try:
                nombre_pdf = f"{codigo_factura}-radicado-{radicado_extraido}.pdf"
                ruta_pdf = subfolder_path / nombre_pdf
                temp_png = subfolder_path / f"temp_{codigo_factura}_{radicado_extraido}.png"
                page.screenshot(path=str(temp_png))
                
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
            logs.append(f"  -> ERROR: No se generó número de radicado. Mensaje: {modal_text.strip()}")
            log_shot = guardar_screenshot_de_error(page, f"error_radicacion_{codigo_factura}")
            logs.append(log_shot)

        # Cerrar el modal con 'Aceptar'
        try:
            btn_aceptar = page.locator("div.modal-content button:has-text('Aceptar'), mok-modal button:has-text('ACEPTAR'), button:has-text('Aceptar')").last
            if btn_aceptar.is_visible(timeout=3000):
                btn_aceptar.click()
                logs.append("  -> Clic en 'Aceptar' del modal de éxito.")
        except Exception:
            pass

        page.wait_for_timeout(2000)
        asegurar_formulario_limpio(page)
        return radicado_extraido, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR en la finalización: {e}"; traceback.print_exc()
        log_screenshot = guardar_screenshot_de_error(page, "error_finalizacion_facturacion")
        logs.append(log_screenshot)
        asegurar_formulario_limpio(page)
        return radicado_extraido, "\n".join(logs + [error_msg])


# ==============================================================================
# --- FUNCIÓN ORQUESTADORA PRINCIPAL ---
# ==============================================================================

def procesar_carpeta(page: Page, subfolder_path: Path, subfolder_name: str, context: str = 'default') -> tuple[str, str | None, str | None, str]:
    """
    Orquesta el flujo completo de radicación de facturación para una carpeta.
    """
    logs = [f"--- Iniciando AXA FACTURACIÓN | Carpeta: '{subfolder_name}' ---"]
    radicado, codigo_factura = None, None
    try:
        # 1. Verificación previa de omisión
        def es_archivo_radicado(f: Path) -> bool:
            name_lower = f.name.lower()
            if name_lower.endswith("-recibido.pdf") or "-radicado" in name_lower:
                return True
            stem = f.stem
            if stem.isdigit() and len(stem) >= 6 and name_lower.endswith(".pdf"):
                return True
            return False

        if any(es_archivo_radicado(f) for f in subfolder_path.iterdir() if f.is_file()):
            return ESTADO_OMITIDO_RADICADO, None, None, "\n".join(logs + ["OMITIENDO: Ya existe radicado en la carpeta."])
            
        # 2. Búsqueda y validación de archivos
        codigo_factura, cuv, archivos_a_subir, docs_log = encontrar_documentos_facturacion_axa(subfolder_path, subfolder_name)
        logs.append(docs_log)
        if not all([codigo_factura, cuv, archivos_a_subir]):
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

        # 3. Preparación de archivos (renombrar PDFs a minúsculas)
        for tipo, path in archivos_a_subir.items():
            if path and path.suffix.lower() == ".pdf":
                path_final, rename_log = asegurar_extension_pdf_minuscula(path)
                archivos_a_subir[tipo] = path_final
                logs.append(rename_log)

        # 4. Proceso de llenado y subida en la web
        asegurar_formulario_limpio(page)
        form_ok, form_log = llenar_formulario(page, codigo_factura, cuv)
        logs.append(form_log)
        if not form_ok:
            asegurar_formulario_limpio(page)
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

        upload_ok, upload_log = subir_archivos_facturacion(page, archivos_a_subir)
        logs.append(upload_log)
        if not upload_ok:
            asegurar_formulario_limpio(page)
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
            
        radicado, final_log = enviar_y_finalizar_radicado(page, subfolder_path, codigo_factura)
        logs.append(final_log)
        if not radicado:
            asegurar_formulario_limpio(page)
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
            
        return ESTADO_EXITO, radicado, codigo_factura, "\n".join(logs)
        
    except Exception as e:
        logs.append(f"ERROR CRÍTICO en el orquestador: {e}")
        traceback.print_exc()
        asegurar_formulario_limpio(page)
        return ESTADO_FALLO, radicado, codigo_factura, "\n".join(logs)