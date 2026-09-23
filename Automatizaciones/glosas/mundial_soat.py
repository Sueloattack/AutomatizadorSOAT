# Automatizaciones/glosas/mundial_soat.py

import os
import re
import sys
import time
import base64
import struct
import hmac
import hashlib
from pathlib import Path
from PIL import Image
from playwright.sync_api import Page, sync_playwright, expect

from Configuracion.constantes import (
    MUNDIAL_SOAT_LOGIN_URL,
    MUNDIAL_SOAT_DEFAULT_USER,
    MUNDIAL_SOAT_DEFAULT_PASS,
    MUNDIAL_SOAT_DEFAULT_TOTP
)
from Core.api_gema import query_api_gema

ESTADO_EXITO = "EXITO"
ESTADO_FALLO = "FALLO"
ESTADO_OMITIDO_RADICADO = "OMITIDO_RAD"
ESTADO_NO_ENCONTRADO = "NO_ENCONTRADO"

def generate_totp_code(secret_key: str) -> str:
    """Genera código TOTP de 6 dígitos según RFC 6238 sin dependencias externas."""
    key = base64.b32decode(secret_key.upper())
    counter = int(time.time() // 30)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[19] & 15
    code = (struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % 1000000
    return f"{code:06d}"

def limpiar_texto(texto: str) -> str:
    """Elimina caracteres de control no imprimibles."""
    if not isinstance(texto, str):
        return str(texto)
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', texto).strip()

def consultar_datos_gema(factura: str, estatus: str, progreso_callback=None) -> dict:
    """
    Consulta información de cabecera, ítems y nota crédito mediante la API HTTP de GEMA.
    """
    match = re.match(r'([A-Za-z]+)(\d+)', factura.strip())
    if not match:
        return {'items': [], 'nc_num': None, 'nc_val': 0}
    serie, docn_str = match.groups()
    docn = int(docn_str)

    try:
        sql_cab = f"gl_docn FROM [gema10.d/salud/datos/glo_cab] WHERE fc_serie = '{serie}' AND fc_docn = {docn} ORDER BY gl_fecha DESC"
        if progreso_callback:
            progreso_callback(f"  [API GEMA] Consultando gl_docn para {factura}...")
        res_cab = query_api_gema(sql_cab)
        if not res_cab:
            return {'items': [], 'nc_num': None, 'nc_val': 0}
        
        gl_docn = res_cab[0]['gl_docn']

        nc_num = None
        nc_val = 0
        if estatus.upper() == 'AI':
            sql_nc = f"docn, valor FROM [gema10.d/CART/DATOS/CAMOVI26] WHERE obligacion = {docn} AND ALLTRIM(serie) = 'NCEG' AND 'AGL-IPS/FRA' $ detalle"
            res_nc = query_api_gema(sql_nc)
            if res_nc:
                nc_num = str(res_nc[0]['docn']).strip()
                nc_val = abs(float(res_nc[0]['valor']))

        sql_det = f"codigo, vr_glosa, motivo_res, estatus1 FROM [gema10.d/salud/datos/glo_det] WHERE gl_docn = {gl_docn} AND estatus1 = '{estatus}'"
        items = query_api_gema(sql_det)
        return {'gl_docn': gl_docn, 'items': items, 'nc_num': nc_num, 'nc_val': nc_val}
    except Exception as e:
        if progreso_callback:
            progreso_callback(f"  ❌ Error en consulta API GEMA ({factura}): {e}")
        return {'items': [], 'nc_num': None, 'nc_val': 0}

def buscar_soporte_pdf(carpeta_base: Path, factura: str) -> str:
    """Busca el archivo de soporte PDF correspondiente a la factura."""
    m = re.match(r'([A-Za-z]+)(\d+)', factura)
    num_str = m.group(2) if m else factura

    candidatos = [
        carpeta_base / num_str / f"{factura}.pdf",
        carpeta_base / factura / f"{factura}.pdf",
        carpeta_base / f"{factura}.pdf"
    ]
    for c in candidatos:
        if c.exists():
            return str(c)

    for f in carpeta_base.rglob(f"{factura}.pdf"):
        return str(f)
    return ""

def guardar_evidencia_rad_pdf(carpeta_base: Path, num_str: str, img_paths: list) -> str:
    """Compila las capturas de pantalla en un documento RAD.pdf de 2 páginas."""
    folder_path = carpeta_base / num_str
    if not folder_path.exists():
        folder_path.mkdir(parents=True, exist_ok=True)
    pdf_dest = folder_path / "RAD.pdf"

    valid_imgs = []
    for p in img_paths:
        if p and Path(p).exists():
            im = Image.open(p)
            if im.mode in ("RGBA", "LA"):
                im = im.convert("RGB")
            valid_imgs.append(im)

    if valid_imgs:
        valid_imgs[0].save(pdf_dest, "PDF", save_all=True, append_images=valid_imgs[1:])
        return str(pdf_dest)
    return ""

def limpiar_modales_y_backdrops(page: Page):
    try:
        page.evaluate("""() => {
            document.querySelectorAll('.modal-backdrop, .swal2-container, ngb-modal-backdrop, .cdk-overlay-backdrop').forEach(el => el.remove());
            document.body.classList.remove('modal-open');
        }""")
    except Exception:
        pass

def login(page: Page, user: str, password: str, totp_secret: str, progreso_callback=None) -> tuple[bool, str]:
    """Inicia sesión y completa la verificación 2FA en HiandGo."""
    logs = [f"Iniciando login en HiandGo para usuario: {user}..."]
    if progreso_callback:
        progreso_callback(logs[-1])
    try:
        page.goto(MUNDIAL_SOAT_LOGIN_URL, wait_until="networkidle", timeout=60000)
        page.locator("input[type='text']").fill(user)
        page.locator("input[type='password']").fill(password)
        page.locator("button:has-text('Entrar')").click()

        page.wait_for_url("**/verify-account", timeout=30000)
        code = generate_totp_code(totp_secret)
        inputs = page.query_selector_all("input[type='text']")
        for idx, d in enumerate(code):
            inputs[idx].fill(d)
        page.locator("button:has-text('Verificar')").click()
        page.wait_for_function("() => !window.location.href.includes('verify-account')", timeout=30000)
        
        page.wait_for_timeout(3000)
        logs.append("  Login y autenticación 2FA exitosos.")
        if progreso_callback:
            progreso_callback(logs[-1])
        return True, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR durante el login en HiandGo: {e}"
        logs.append(error_msg)
        if progreso_callback:
            progreso_callback(error_msg)
        return False, "\n".join(logs)

def navegar_a_seccion(page: Page, seccion: str):
    """Navega a la sección requerida (parciales, totales, devoluciones)."""
    limpiar_modales_y_backdrops(page)
    menu_parent = page.locator("a:has-text('Respuesta a Obj y Dev')")
    if menu_parent.count() > 0 and menu_parent.is_visible():
        menu_parent.click()
        page.wait_for_timeout(1000)

    if seccion == 'totales':
        target_name = "Objeciones Totales"
        url = "https://hiandgo.iq-online.net.co/totalReconsideration/total-reconsiderations"
    elif seccion == 'devoluciones':
        target_name = "Devoluciones"
        url = "https://hiandgo.iq-online.net.co/reconsiderationDevolutions/reconsideration-devolutions"
    else:
        target_name = "Objeciones Parciales"
        url = "https://hiandgo.iq-online.net.co/partialReconsideration/partial-reconsiderations"

    sub = page.locator(f"a:has-text('{target_name}')")
    if sub.count() > 0 and sub.is_visible():
        sub.click()
    else:
        page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(3000)

def adjuntar_soporte_modal(page: Page, soporte_path: str, tipo_doc: str = "Anexos", num_nota: str = "", valor_nota: str = "") -> bool:
    """Adjunta el documento de soporte en el modal de documentos."""
    add_btn = page.locator("button:has-text('Adicionar')")
    if add_btn.count() == 0:
        return False

    add_btn.first.click()
    page.wait_for_timeout(2000)

    modal_doc = page.locator(".modal, mat-dialog-container, div[role='dialog']").first
    if modal_doc.count() == 0:
        return False

    tipo_select = modal_doc.locator("ng-select").nth(1)
    tipo_select.click()
    page.wait_for_timeout(500)

    search_inp = tipo_select.locator("input")
    search_inp.fill(tipo_doc[:4])
    page.wait_for_timeout(500)
    anex_opt = page.locator(f".ng-option:has-text('{tipo_doc}')")
    if anex_opt.count() > 0:
        anex_opt.first.click()
    else:
        page.locator(".ng-option").first.click()
    page.wait_for_timeout(500)

    if tipo_doc == "Nota Crédito":
        inputs = modal_doc.locator("input[type='text']")
        if inputs.count() >= 3:
            inputs.nth(1).fill(str(num_nota))
            inputs.nth(2).fill(str(valor_nota))

    modal_doc.locator("input[type='file']").set_input_files(soporte_path)
    page.wait_for_timeout(2000)

    guardar_btn = modal_doc.locator("button:has-text('Guardar')")
    if not guardar_btn.is_disabled():
        guardar_btn.click()
        try:
            modal_doc.wait_for(state="detached", timeout=35000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        return True
    return False

def radicar_factura_mundial(page: Page, factura: str, estatus: str, carpeta_base: Path, progreso_callback=None) -> tuple[str, str]:
    """Radica una factura individual en HiandGo."""
    log = []
    def log_msg(m):
        log.append(m)
        if progreso_callback:
            progreso_callback(m)

    log_msg(f"\n=======================================================")
    log_msg(f"Procesando Factura: {factura} [Estatus: {estatus}]")
    log_msg(f"=======================================================")

    m = re.match(r'([A-Za-z]+)(\d+)', factura)
    num_str = m.group(2) if m else factura

    # 1. Comprobar si ya existe RAD.pdf
    rad_existente = carpeta_base / num_str / "RAD.pdf"
    if rad_existente.exists():
        log_msg(f"  -> OMITIDA: Ya tiene soporte RAD.pdf en {rad_existente}")
        return ESTADO_OMITIDO_RADICADO, "\n".join(log)

    # 2. Consultar datos en GEMA vía API
    gema_data = consultar_datos_gema(factura, estatus, progreso_callback)
    soporte_pdf = buscar_soporte_pdf(carpeta_base, factura)
    if not soporte_pdf:
        log_msg(f"  ❌ No se encontró el soporte PDF para la factura {factura}")
        return ESTADO_FALLO, "\n".join(log)
    log_msg(f"  -> Soporte PDF: {soporte_pdf}")

    # 3. Buscar factura en parciales primero, luego totales / devoluciones
    secciones_a_probar = ['parciales', 'totales', 'devoluciones']
    seccion_encontrada = None
    row_encontrada = None

    for sec in secciones_a_probar:
        navegar_a_seccion(page, sec)
        search_inp = page.locator("input[placeholder*='Buscar' i], input[type='search']").first
        search_inp.click()
        search_inp.fill(factura)
        search_inp.press('Enter')
        page.wait_for_timeout(3000)

        row = page.locator(f"table tbody tr:has-text('{factura}')")
        if row.count() > 0:
            seccion_encontrada = sec
            row_encontrada = row.first
            log_msg(f"  -> Factura encontrada en la sección '{sec}'!")
            break

    if not seccion_encontrada:
        log_msg(f"  ❌ Factura {factura} NO ENCONTRADA en ninguna bandeja de la plataforma.")
        return ESTADO_NO_ENCONTRADO, "\n".join(log)

    # 4. Entrar al detalle
    row_encontrada.locator("mat-icon:has-text('visibility'), td").first.click()
    page.wait_for_timeout(5000)

    temp_img1 = str(carpeta_base / num_str / f"temp_det_{factura}.png")
    temp_img2 = str(carpeta_base / num_str / f"temp_post_{factura}.png")

    if seccion_encontrada == 'parciales':
        # Expandir atenciones colapsadas
        expand_buttons = page.locator("button[aria-label='expand row'], button:has(mat-icon:has-text('keyboard_arrow_down'))")
        cnt_exp = expand_buttons.count()
        for exp_idx in range(cnt_exp):
            btn = expand_buttons.nth(exp_idx)
            if btn.is_visible():
                btn.click()
                page.wait_for_timeout(1500)

        # Ajustar paginadores
        for pag in page.locator("select.paginator__rows-select").all():
            try:
                pag.select_option("100")
                page.wait_for_timeout(500)
            except Exception:
                pass

        sub_table = page.locator("table table").first
        if sub_table.count() == 0:
            sub_table = page.locator("table").nth(1)

        # Responder por lote si existe el botón Responder
        header_cb = sub_table.locator("thead th").first
        if header_cb.count() > 0:
            header_cb.click()
            page.wait_for_timeout(1000)

        responder_btn = page.locator("button:has-text('Responder')").first
        if responder_btn.count() > 0 and not responder_btn.is_disabled():
            responder_btn.click()
            page.wait_for_timeout(2000)
            modal = page.locator(".modal, mat-dialog-container, div[role='dialog']").first
            if modal.is_visible():
                tipo_resp_txt = "Acepta" if estatus.upper() == 'AI' else "No Acepta"
                modal.locator("ng-select").first.click()
                page.wait_for_timeout(500)
                page.locator(f".ng-option:has-text('{tipo_resp_txt}')").first.click()
                page.wait_for_timeout(800)

                items = gema_data.get('items', [])
                motivo_full = " ".join([it['motivo_res'] for it in items if it.get('motivo_res')]) if items else ""
                if not motivo_full:
                    motivo_full = "No se acepta glosa, de acuerdo a la historia clinica y manual tarifario decreto 2423 de 1996."
                motivo_clean = limpiar_texto(motivo_full)[:950]

                modal.locator("textarea").fill(motivo_clean)
                page.wait_for_timeout(500)

                btn_g = modal.locator("button:has-text('Guardar')")
                if not btn_g.is_disabled():
                    btn_g.click()
                    try:
                        modal.wait_for(state="detached", timeout=20000)
                    except Exception:
                        pass
                    page.wait_for_timeout(2000)
                    log_msg("  -> Respuesta de ítems guardada con éxito.")

        # Adjuntar documento
        tipo_soporte = "Nota Crédito" if estatus.upper() == 'AI' and gema_data.get('nc_num') else "Anexos"
        adjuntar_soporte_modal(
            page, soporte_pdf, 
            tipo_doc=tipo_soporte,
            num_nota=gema_data.get('nc_num', ''),
            valor_nota=str(gema_data.get('nc_val', ''))
        )

        page.screenshot(path=temp_img1, full_page=True)

        # Click Guardar general
        guardar_btn = page.locator("button:has-text('Guardar')").last
        guardar_btn.click()
        page.wait_for_timeout(3000)

        # Confirmación de envío
        popup = page.locator(".swal2-container, .modal, mat-dialog-container, div[role='dialog']").first
        if popup.is_visible():
            confirm_btn = popup.locator("button:has-text('Aceptar'), button:has-text('Sí'), button:has-text('Confirmar'), .swal2-confirm")
            if confirm_btn.count() > 0:
                confirm_btn.first.click()
                page.wait_for_timeout(8000)

        page.screenshot(path=temp_img2, full_page=True)
        guardar_evidencia_rad_pdf(carpeta_base, num_str, [temp_img1, temp_img2])

        # Verificación en bandeja
        navegar_a_seccion(page, 'parciales')
        search_inp = page.locator("input[placeholder*='Buscar' i], input[type='search']").first
        search_inp.click()
        search_inp.fill(factura)
        search_inp.press('Enter')
        page.wait_for_timeout(3000)

        if page.locator(f"table tbody tr:has-text('{factura}')").count() == 0:
            log_msg(f"  🎉 RADICACIÓN EXITOSA: {factura} radicada y removida de la bandeja.")
            return ESTADO_EXITO, "\n".join(log)
        else:
            log_msg(f"  ⚠️ Advertencia: {factura} aún figura en bandeja.")
            return ESTADO_FALLO, "\n".join(log)

    else:
        # Totales o Devoluciones
        log_msg(f"  -> Procesando formulario de {seccion_encontrada}...")
        adjuntar_soporte_modal(page, soporte_pdf, tipo_doc="Anexos")
        
        textareas = page.locator("textarea")
        if textareas.count() > 0:
            items = gema_data.get('items', [])
            motivo = items[0]['motivo_res'] if items and items[0].get('motivo_res') else "No se acepta la objeción de acuerdo a los soportes clínicos adjuntos."
            textareas.first.fill(limpiar_texto(motivo)[:950])

        page.screenshot(path=temp_img1, full_page=True)

        guardar_btn = page.locator("button:has-text('Guardar')").last
        guardar_btn.click()
        page.wait_for_timeout(3000)

        popup = page.locator(".swal2-container, .modal, mat-dialog-container, div[role='dialog']").first
        if popup.is_visible():
            confirm_btn = popup.locator("button:has-text('Aceptar'), button:has-text('Sí'), button:has-text('Confirmar'), .swal2-confirm")
            if confirm_btn.count() > 0:
                confirm_btn.first.click()
                page.wait_for_timeout(8000)

        page.screenshot(path=temp_img2, full_page=True)
        guardar_evidencia_rad_pdf(carpeta_base, num_str, [temp_img1, temp_img2])
        log_msg(f"  🎉 RADICACIÓN EXITOSA: {factura} enviada.")
        return ESTADO_EXITO, "\n".join(log)

def procesar_glosas_mundial_soat(carpeta_soportes: str, lista_glosas_texto: str, progreso_callback, headless: bool = True):
    """
    Función principal orquestadora para Mundial SOAT.
    """
    carpeta_base = Path(carpeta_soportes).resolve()
    glosas_a_procesar = []

    for linea in lista_glosas_texto.strip().split('\n'):
        partes = linea.strip().split()
        if len(partes) >= 2:
            glosas_a_procesar.append((partes[0].upper(), partes[1].upper()))
        elif len(partes) == 1 and partes[0]:
            glosas_a_procesar.append((partes[0].upper(), "C1"))

    if not glosas_a_procesar:
        progreso_callback("❌ No hay facturas válidas en la lista ingresada.")
        return 0, 0, 0, 0, []

    progreso_callback(f"[INFO] Se procesarán {len(glosas_a_procesar)} facturas para Mundial SOAT...")
    progreso_callback(f"[INFO] Carpeta de soportes: {carpeta_base}")

    exitos = 0
    fallos = 0
    omit_rad = 0
    no_encontradas = 0
    reporte = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})

        login_ok, login_log = login(
            page, 
            MUNDIAL_SOAT_DEFAULT_USER, 
            MUNDIAL_SOAT_DEFAULT_PASS, 
            MUNDIAL_SOAT_DEFAULT_TOTP, 
            progreso_callback
        )
        if not login_ok:
            browser.close()
            return 0, len(glosas_a_procesar), 0, 0, ["Login fallido en HiandGo."]

        for idx, (factura, estatus) in enumerate(glosas_a_procesar):
            progreso_callback(f"\n>>> [{idx+1}/{len(glosas_a_procesar)}] {factura} ({estatus})")
            estado, detalle_log = radicar_factura_mundial(
                page, factura, estatus, carpeta_base, progreso_callback
            )
            reporte.append(f"{factura} [{estatus}]: {estado}")

            if estado == ESTADO_EXITO:
                exitos += 1
            elif estado == ESTADO_OMITIDO_RADICADO:
                omit_rad += 1
            elif estado == ESTADO_NO_ENCONTRADO:
                no_encontradas += 1
                fallos += 1
            else:
                fallos += 1

        browser.close()

    return exitos, fallos, omit_rad, no_encontradas, reporte
