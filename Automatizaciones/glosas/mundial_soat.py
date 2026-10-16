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
ESTADO_SIN_RESERVA = "SIN_RESERVA"
ESTADO_SIN_OBJECIONES = "SIN_OBJECIONES"

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

def buscar_soporte_pdf(carpeta_base: Path, factura: str, es_nc: bool = False) -> str:
    """Busca el archivo de soporte PDF correspondiente a la factura o la nota crédito."""
    m = re.match(r'([A-Za-z]+)(\d+)', factura)
    num_str = m.group(2) if m else factura
    carpeta_fac = carpeta_base / num_str

    if es_nc and carpeta_fac.exists():
        for nc_pattern in ["NC*.pdf", "*NC*.pdf", "*Nota*Credito*.pdf"]:
            nc_files = list(carpeta_fac.glob(nc_pattern))
            if nc_files:
                return str(nc_files[0])

    candidatos = [
        carpeta_base / num_str / f"{factura}.pdf",
        carpeta_base / num_str / f"{factura}-soporte.pdf",
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
        # Cerrar primero cualquier modal que tenga botón cancelar
        cancel_btns = page.locator("mat-dialog-container button:has-text('Cancelar'), .modal button:has-text('Cancelar')")
        for i in range(cancel_btns.count()):
            try:
                if cancel_btns.nth(i).is_visible():
                    cancel_btns.nth(i).click(timeout=1000)
            except Exception:
                pass

        page.evaluate("""() => {
            document.querySelectorAll('.modal-backdrop, .swal2-container, ngb-modal-backdrop, .cdk-overlay-backdrop, .cdk-overlay-pane, mat-dialog-container, .modal').forEach(el => el.remove());
            document.querySelectorAll('.cdk-overlay-container').forEach(c => c.innerHTML = '');
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

def navegar_a_seccion(page: Page, seccion: str, force_reload: bool = False):
    """Navega a la sección requerida (parciales, totales) asegurando volver a la tabla principal."""
    limpiar_modales_y_backdrops(page)

    if seccion == 'totales':
        target_fragment = "total-reconsiderations"
        url = "https://hiandgo.iq-online.net.co/totalReconsideration/total-reconsiderations"
    elif seccion == 'devoluciones':
        target_fragment = "reconsideration-devolutions"
        url = "https://hiandgo.iq-online.net.co/reconsiderationDevolutions/reconsideration-devolutions"
    else:
        target_fragment = "partial-reconsiderations"
        url = "https://hiandgo.iq-online.net.co/partialReconsideration/partial-reconsiderations"

    # Verificar si estamos actualmente dentro de la vista de detalle de una factura
    en_detalle = False
    try:
        en_detalle = page.evaluate("""() => {
            const txt = document.body.innerText || '';
            return txt.includes('Datos de la factura') || txt.includes('Respuesta Objeción');
        }""")
    except Exception:
        pass

    # Si estamos en la URL, NO estamos en detalle, NO es force_reload y la tabla principal está visible:
    if not force_reload and not en_detalle and target_fragment in page.url:
        tabla_th = page.locator("table th:has-text('NÚMERO DE FACTURA'), table th:has-text('Radicación')")
        if tabla_th.count() > 0 and tabla_th.first.is_visible():
            return

    # Si estamos en detalle o en otra URL o force_reload, navegar mediante clic de menú
    clicked = page.evaluate("""(target) => {
        const links = Array.from(document.querySelectorAll('a'));
        const link = links.find(a => a.getAttribute('href') && a.getAttribute('href').includes(target));
        if (link) {
            link.click();
            return true;
        }
        return false;
    }""", target_fragment)

    if not clicked:
        try:
            menu_parent = page.locator("a:has-text('Respuesta a Obj y Dev')")
            if menu_parent.count() > 0:
                menu_parent.first.click()
                page.wait_for_timeout(1000)
                clicked = page.evaluate("""(target) => {
                    const links = Array.from(document.querySelectorAll('a'));
                    const link = links.find(a => a.getAttribute('href') && a.getAttribute('href').includes(target));
                    if (link) {
                        link.click();
                        return true;
                    }
                    return false;
                }""", target_fragment)
        except Exception:
            pass

    page.wait_for_timeout(2500)

    # Verificar si la tabla principal quedó visible; si no, recargar página
    tabla_ok = False
    try:
        tabla_th = page.locator("table th:has-text('NÚMERO DE FACTURA'), table th:has-text('Radicación')")
        tabla_ok = tabla_th.count() > 0 and tabla_th.first.is_visible()
    except Exception:
        pass

    if not tabla_ok:
        try:
            page.goto(url, wait_until="networkidle", timeout=35000)
            page.wait_for_timeout(2500)
        except Exception:
            pass

def adjuntar_soporte_modal(page: Page, soporte_path: str, tipo_doc: str = "Anexos", num_nota: str = "", valor_nota: str = "") -> bool:
    """Adjunta el documento de soporte en el modal de documentos."""
    add_btn = page.locator("button:has-text('Adicionar')")
    if add_btn.count() == 0:
        return False

    add_btn.first.click()
    page.wait_for_timeout(2000)

    modal_doc = page.locator(".modal, mat-dialog-container, div[role='dialog']").first
    if modal_doc.count() == 0 or not modal_doc.is_visible():
        return False

    # Seleccionar tipo documental en ng-select (es el segundo ng-select del modal)
    ng_selects = modal_doc.locator("ng-select")
    if ng_selects.count() >= 2:
        tipo_select = ng_selects.nth(1)
    else:
        tipo_select = ng_selects.first

    tipo_select.click()
    page.wait_for_timeout(500)

    is_nc = "nota" in tipo_doc.lower()
    search_inp = tipo_select.locator("input")
    search_term = "Nota" if is_nc else "Anex"
    search_inp.fill(search_term)
    page.wait_for_timeout(800)

    if is_nc:
        opt = page.locator(".ng-option:has-text('Nota Crédito'), .ng-option:has-text('Nota Cr'), .ng-option:has-text('Nota')").first
    else:
        opt = page.locator(".ng-option:has-text('Anexos'), .ng-option:has-text('Anexo')").first

    if opt.count() > 0 and opt.is_visible():
        opt.click()
    else:
        page.locator(".ng-option").first.click()
    page.wait_for_timeout(1000)

    # Si es Nota Crédito, llenar Número y Valor en los inputs específicos input.iq-input-control
    if is_nc:
        nc_inputs = modal_doc.locator("input.iq-input-control")
        if nc_inputs.count() >= 2:
            nc_inputs.nth(0).fill(str(num_nota))
            nc_inputs.nth(0).dispatch_event("input")
            nc_inputs.nth(0).dispatch_event("change")
            nc_inputs.nth(0).dispatch_event("blur")

            try:
                val_clean = str(int(float(valor_nota)))
            except Exception:
                val_clean = str(valor_nota)
            nc_inputs.nth(1).fill(val_clean)
            nc_inputs.nth(1).dispatch_event("input")
            nc_inputs.nth(1).dispatch_event("change")
            nc_inputs.nth(1).dispatch_event("blur")
            page.wait_for_timeout(500)

    modal_doc.locator("input[type='file']").set_input_files(soporte_path)
    page.wait_for_timeout(2500)

    guardar_btn = modal_doc.locator("button:has-text('Guardar')")
    if guardar_btn.count() > 0 and not guardar_btn.is_disabled():
        guardar_btn.click()
        try:
            modal_doc.wait_for(state="detached", timeout=25000)
        except Exception:
            pass
        page.wait_for_timeout(2500)
        return True
    else:
        # Cerrar el modal para evitar dejarlo abierto bloqueando la interfaz
        btn_cancel = modal_doc.locator("button:has-text('Cancelar'), .btn-close-modal, [aria-label='Close']")
        if btn_cancel.count() > 0 and btn_cancel.first.is_visible():
            btn_cancel.first.click()
        page.wait_for_timeout(1000)
        return False

def radicar_factura_mundial(page: Page, factura: str, estatus: str, carpeta_base: Path, progreso_callback=None) -> tuple[str, str]:
    """Radica una factura individual en HiandGo."""
    log = []
    def log_msg(m):
        log.append(m)
        if progreso_callback:
            progreso_callback(m)

    limpiar_modales_y_backdrops(page)

    log_msg(f"\n=======================================================")
    log_msg(f"Procesando Factura: {factura} [Estatus: {estatus}]")
    log_msg(f"=======================================================")

    m = re.match(r'([A-Za-z]+)(\d+)', factura)
    num_str = m.group(2) if m else factura
    carpeta_fac = carpeta_base / num_str
    carpeta_fac.mkdir(parents=True, exist_ok=True)

    temp_img1 = str(carpeta_fac / f"temp_det_{factura}.png")
    temp_img2 = str(carpeta_fac / f"temp_post_{factura}.png")
    error_img = str(carpeta_fac / f"ERROR_{factura}.png")

    def registrar_error(motivo_log, capturar=True, estado_ret=ESTADO_FALLO):
        log_msg(motivo_log)
        if capturar:
            try:
                page.screenshot(path=error_img, full_page=True)
            except Exception:
                pass
        # Eliminar RAD.pdf falso y capturas temporales si existieran
        (carpeta_fac / "RAD.pdf").unlink(missing_ok=True)
        if Path(temp_img1).exists():
            Path(temp_img1).unlink(missing_ok=True)
        if Path(temp_img2).exists():
            Path(temp_img2).unlink(missing_ok=True)
        limpiar_modales_y_backdrops(page)
        return estado_ret, "\n".join(log)

    def registrar_exito():
        log_msg(f"  [EXITO] RADICACION EXITOSA: {factura} radicada y removida de la bandeja.")
        # Compilar RAD.pdf con temp_img1 y temp_img2
        guardar_evidencia_rad_pdf(carpeta_base, num_str, [temp_img1, temp_img2])
        # Limpiar temporales
        if Path(temp_img1).exists():
            Path(temp_img1).unlink(missing_ok=True)
        if Path(temp_img2).exists():
            Path(temp_img2).unlink(missing_ok=True)
        # Limpiar imagen de error previa si existía
        if Path(error_img).exists():
            Path(error_img).unlink(missing_ok=True)
        return ESTADO_EXITO, "\n".join(log)

    # 1. Comprobar si ya existe RAD.pdf
    rad_existente = carpeta_fac / "RAD.pdf"
    if rad_existente.exists():
        log_msg(f"  -> OMITIDA: Ya tiene soporte RAD.pdf en {rad_existente}")
        return ESTADO_OMITIDO_RADICADO, "\n".join(log)

    # 2. Consultar datos en GEMA vía API
    gema_data = consultar_datos_gema(factura, estatus, progreso_callback)
    tipo_soporte = "Nota Crédito" if estatus.upper() == 'AI' and gema_data.get('nc_num') else "Anexos"
    es_nc = (tipo_soporte == "Nota Crédito")

    soporte_pdf = buscar_soporte_pdf(carpeta_base, factura, es_nc=es_nc)
    if not soporte_pdf:
        return registrar_error(f"  [ERROR] No se encontró el soporte PDF para la factura {factura}", capturar=False)
    log_msg(f"  -> Soporte PDF: {soporte_pdf} (Tipo: {tipo_soporte})")

    # 3. Buscar factura en parciales primero, luego totales
    secciones_a_probar = ['parciales', 'totales']
    seccion_encontrada = None
    row_encontrada = None

    for sec in secciones_a_probar:
        navegar_a_seccion(page, sec)
        search_inp = page.locator("input[placeholder*='Buscar' i], input[type='search']").first
        if search_inp.count() == 0 or not search_inp.is_visible():
            page.wait_for_timeout(2000)
            search_inp = page.locator("input[placeholder*='Buscar' i], input[type='search']").first

        search_inp.click()
        search_inp.fill("")
        search_inp.fill(factura)
        search_inp.press('Enter')
        page.wait_for_timeout(3000)

        # Chequeo si aparece mensaje de no objeciones en la bandeja
        toast = page.locator(".toast, .toast-message, .swal2-container, .alert").first
        if toast.count() > 0 and toast.is_visible():
            t_txt = toast.inner_text().lower()
            if "no tiene objeciones" in t_txt:
                return registrar_error(f"  [ERROR] PLATAFORMA: {toast.inner_text().strip()}", capturar=True, estado_ret=ESTADO_SIN_OBJECIONES)

        row = page.locator(f"table tbody tr:has-text('{factura}')")
        if row.count() > 0:
            seccion_encontrada = sec
            row_encontrada = row.first
            log_msg(f"  -> Factura encontrada en la sección '{sec}'!")
            break

    if not seccion_encontrada:
        return registrar_error(f"  [ERROR] Factura {factura} NO ENCONTRADA en ninguna bandeja de la plataforma.", capturar=True, estado_ret=ESTADO_NO_ENCONTRADO)

    # 4. Entrar al detalle
    row_encontrada.locator("mat-icon:has-text('visibility'), td").first.click()
    page.wait_for_timeout(4000)

    # Chequeo si al abrir sale mensaje de no objeciones o sin reserva
    toast = page.locator(".toast, .toast-message, .swal2-container, .alert").first
    if toast.count() > 0 and toast.is_visible():
        t_txt = toast.inner_text().lower()
        if "no tiene objeciones" in t_txt:
            return registrar_error(f"  [ERROR] PLATAFORMA: {toast.inner_text().strip()}", capturar=True, estado_ret=ESTADO_SIN_OBJECIONES)
        if any(term in t_txt for term in ["sin reserva", "no existe reserva", "agotamiento", "cobertura"]):
            return registrar_error(f"  [ERROR] BLOQUEADA POR PLATAFORMA: {toast.inner_text().strip()}", capturar=True, estado_ret=ESTADO_SIN_RESERVA)

    if seccion_encontrada == 'parciales':
        # Expandir atenciones colapsadas
        expand_buttons = page.locator("button[aria-label='expand row'], button:has(mat-icon:has-text('keyboard_arrow_down'))")
        cnt_exp = expand_buttons.count()
        for exp_idx in range(cnt_exp):
            btn = expand_buttons.nth(exp_idx)
            if btn.is_visible():
                btn.click()
                page.wait_for_timeout(800)

        # Ajustar paginadores a 100
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

        # Adjuntar documento soporte
        adj_ok = adjuntar_soporte_modal(
            page, soporte_pdf, 
            tipo_doc=tipo_soporte,
            num_nota=gema_data.get('nc_num', ''),
            valor_nota=str(gema_data.get('nc_val', ''))
        )
        if not adj_ok:
            log_msg("  [ADVERTENCIA] Falló o no fue requerido adjuntar documento en modal.")

        page.screenshot(path=temp_img1, full_page=True)

        # Click Guardar general
        guardar_btn = page.locator("button:has-text('Guardar')").last
        guardar_btn.click()
        page.wait_for_timeout(3000)

        # Confirmación de envío o detección de Sin Reserva / Sin Objeciones
        popup = page.locator(".swal2-container, .modal, mat-dialog-container, div[role='dialog'], .toast").first
        if popup.count() > 0 and popup.is_visible():
            popup_txt = popup.inner_text()
            txt_l = popup_txt.lower()
            if "no tiene objeciones" in txt_l:
                return registrar_error(f"  [ERROR] PLATAFORMA: {popup_txt.strip()}", capturar=True, estado_ret=ESTADO_SIN_OBJECIONES)
            if any(term in txt_l for term in ["sin reserva", "agotamiento", "cobertura", "no existe reserva"]):
                return registrar_error(f"  [ERROR] BLOQUEADA POR PLATAFORMA: {popup_txt.strip()}", capturar=True, estado_ret=ESTADO_SIN_RESERVA)

            confirm_btn = popup.locator("button:has-text('Aceptar'), button:has-text('Sí'), button:has-text('Confirmar'), .swal2-confirm")
            if confirm_btn.count() > 0 and confirm_btn.first.is_visible():
                confirm_btn.first.click()
                page.wait_for_timeout(6000)

        # Detección posterior a confirmación
        post_popup = page.locator(".swal2-container, .modal, mat-dialog-container, div[role='dialog'], .toast").first
        if post_popup.count() > 0 and post_popup.is_visible():
            post_txt = post_popup.inner_text()
            txt_l = post_txt.lower()
            if "no tiene objeciones" in txt_l:
                return registrar_error(f"  [ERROR] PLATAFORMA: {post_txt.strip()}", capturar=True, estado_ret=ESTADO_SIN_OBJECIONES)
            if any(term in txt_l for term in ["sin reserva", "agotamiento", "cobertura", "no existe reserva"]):
                return registrar_error(f"  [ERROR] BLOQUEADA POR PLATAFORMA: {post_txt.strip()}", capturar=True, estado_ret=ESTADO_SIN_RESERVA)

            btn_close = post_popup.locator("button:has-text('Aceptar'), button:has-text('Entendido'), button:has-text('Ok'), .swal2-confirm")
            if btn_close.count() > 0 and btn_close.first.is_visible():
                btn_close.first.click()
                page.wait_for_timeout(1000)

        page.screenshot(path=temp_img2, full_page=True)

        # Verificación en bandeja
        navegar_a_seccion(page, 'parciales', force_reload=True)
        search_inp = page.locator("input[placeholder*='Buscar' i], input[type='search']").first
        search_inp.click()
        search_inp.fill("")
        search_inp.fill(factura)
        search_inp.press('Enter')
        page.wait_for_timeout(3000)

        if page.locator(f"table tbody tr:has-text('{factura}')").count() == 0:
            return registrar_exito()
        else:
            return registrar_error(f"  [ALERTA] {factura} aún figura en bandeja tras radicación.", capturar=True, estado_ret=ESTADO_FALLO)

    else:
        # Totales
        log_msg(f"  -> Procesando formulario de {seccion_encontrada}...")
        
        # 1. Responder objeción mediante el botón en la fila
        btn_responder = page.locator("button[title='Responder'], button:has-text('Responder')").first
        if btn_responder.count() > 0 and btn_responder.is_visible():
            btn_responder.click()
            page.wait_for_timeout(2000)
            modal = page.locator(".modal, mat-dialog-container, div[role='dialog']").first
            if modal.is_visible():
                tipo_resp_txt = "Acepta" if estatus.upper() == 'AI' else "No Acepta"
                modal.locator("ng-select").first.click()
                page.wait_for_timeout(500)
                page.locator(f".ng-option:has-text('{tipo_resp_txt}')").first.click()
                page.wait_for_timeout(800)

                items = gema_data.get('items', [])
                motivo = items[0]['motivo_res'] if items and items[0].get('motivo_res') else "No se acepta la objeción de acuerdo a los soportes clínicos adjuntos."
                motivo_clean = limpiar_texto(motivo)[:950]

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
                    log_msg("  -> Respuesta de objeción guardada con éxito.")

        # 2. Adjuntar documento soporte
        adj_ok = adjuntar_soporte_modal(
            page, soporte_pdf, 
            tipo_doc=tipo_soporte,
            num_nota=gema_data.get('nc_num', ''),
            valor_nota=str(gema_data.get('nc_val', ''))
        )
        if not adj_ok:
            log_msg("  [ADVERTENCIA] Falló o no fue requerido adjuntar documento en modal.")

        page.screenshot(path=temp_img1, full_page=True)

        # 3. Guardar general
        guardar_btn = page.locator("button:has-text('Guardar')").last
        guardar_btn.click()
        page.wait_for_timeout(3000)

        popup = page.locator(".swal2-container, .modal, mat-dialog-container, div[role='dialog'], .toast").first
        if popup.count() > 0 and popup.is_visible():
            popup_txt = popup.inner_text()
            txt_l = popup_txt.lower()
            if "no tiene objeciones" in txt_l:
                return registrar_error(f"  [ERROR] PLATAFORMA: {popup_txt.strip()}", capturar=True, estado_ret=ESTADO_SIN_OBJECIONES)
            if any(term in txt_l for term in ["sin reserva", "agotamiento", "cobertura", "no existe reserva"]):
                return registrar_error(f"  [ERROR] BLOQUEADA POR PLATAFORMA: {popup_txt.strip()}", capturar=True, estado_ret=ESTADO_SIN_RESERVA)

            confirm_btn = popup.locator("button:has-text('Aceptar'), button:has-text('Sí'), button:has-text('Confirmar'), .swal2-confirm")
            if confirm_btn.count() > 0 and confirm_btn.first.is_visible():
                confirm_btn.first.click()
                page.wait_for_timeout(6000)

        post_popup = page.locator(".swal2-container, .modal, mat-dialog-container, div[role='dialog'], .toast").first
        if post_popup.count() > 0 and post_popup.is_visible():
            post_txt = post_popup.inner_text()
            txt_l = post_txt.lower()
            if "no tiene objeciones" in txt_l:
                return registrar_error(f"  [ERROR] PLATAFORMA: {post_txt.strip()}", capturar=True, estado_ret=ESTADO_SIN_OBJECIONES)
            if any(term in txt_l for term in ["sin reserva", "agotamiento", "cobertura", "no existe reserva"]):
                return registrar_error(f"  [ERROR] BLOQUEADA POR PLATAFORMA: {post_txt.strip()}", capturar=True, estado_ret=ESTADO_SIN_RESERVA)

            btn_close = post_popup.locator("button:has-text('Aceptar'), button:has-text('Entendido'), button:has-text('Ok'), .swal2-confirm")
            if btn_close.count() > 0 and btn_close.first.is_visible():
                btn_close.first.click()
                page.wait_for_timeout(1000)

        page.screenshot(path=temp_img2, full_page=True)

        # 4. Verificación en bandeja
        navegar_a_seccion(page, 'totales', force_reload=True)
        search_inp = page.locator("input[placeholder*='Buscar' i], input[type='search']").first
        search_inp.click()
        search_inp.fill("")
        search_inp.fill(factura)
        search_inp.press('Enter')
        page.wait_for_timeout(3000)

        if page.locator(f"table tbody tr:has-text('{factura}')").count() == 0:
            return registrar_exito()
        else:
            return registrar_error(f"  [ALERTA] {factura} aún figura en bandeja tras radicación.", capturar=True, estado_ret=ESTADO_FALLO)

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
        progreso_callback("[ERROR] No hay facturas validas en la lista ingresada.")
        return 0, 0, 0, 0, []

    progreso_callback(f"[INFO] Se procesaran {len(glosas_a_procesar)} facturas para Mundial SOAT...")
    progreso_callback(f"[INFO] Carpeta de soportes: {carpeta_base}")

    exitos = 0
    fallos = 0
    omit_rad = 0
    no_encontradas = 0
    sin_reserva = 0
    sin_objeciones = 0
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
            try:
                estado, detalle_log = radicar_factura_mundial(
                    page, factura, estatus, carpeta_base, progreso_callback
                )
            except Exception as e:
                import traceback
                err_tb = traceback.format_exc()
                progreso_callback(f"  [ERROR] ERROR INESPERADO procesando {factura}: {e}\n{err_tb}")
                estado = ESTADO_FALLO
                limpiar_modales_y_backdrops(page)

            reporte.append(f"{factura} [{estatus}]: {estado}")
            limpiar_modales_y_backdrops(page)

            if estado == ESTADO_EXITO:
                exitos += 1
            elif estado == ESTADO_OMITIDO_RADICADO:
                omit_rad += 1
            elif estado == ESTADO_NO_ENCONTRADO:
                no_encontradas += 1
                fallos += 1
            elif estado == ESTADO_SIN_RESERVA:
                sin_reserva += 1
                fallos += 1
            elif estado == ESTADO_SIN_OBJECIONES:
                sin_objeciones += 1
                fallos += 1
            else:
                fallos += 1

        browser.close()

    progreso_callback(f"\n[RESUMEN FINAL] Exitos: {exitos} | Omitidas (ya radicadas): {omit_rad} | Sin Objeciones: {sin_objeciones} | Sin Reserva: {sin_reserva} | No encontradas: {no_encontradas} | Otros Fallos: {fallos - no_encontradas - sin_reserva - sin_objeciones}")
    return exitos, fallos, omit_rad, no_encontradas, reporte


