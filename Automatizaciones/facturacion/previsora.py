# AutomatizadorSOAT/Automatizaciones/facturacion/previsora.py

import time
import traceback
from pathlib import Path

from playwright.sync_api import Page, expect
try:
    from Configuracion.constantes import *
    # IMPORTANTE: Llamamos a nuestra nueva función de utilidades
    from Core.utilidades import encontrar_documentos_facturacion
except ImportError as e:
    raise ImportError(f"ERROR CRITICO: No se pudieron importar módulos: {e}")

# Estados consistentes
ESTADO_EXITO = "EXITO"
ESTADO_FALLO = "FALLO"
ESTADO_OMITIDO_RADICADO = "OMITIDO_RADICADO"

# Las funciones de login y navegar_a_inicio son idénticas a las de glosas
# Para no duplicar código, podrías crear un "Automatizaciones/previsora_base.py"
# Pero por ahora, es más claro tenerlas aquí.

def login(page: Page) -> tuple[bool, str]:
    # (Pega aquí tu función login() del previsora.py de glosas. Es idéntica)
    # ...
    logs = ["Iniciando login con Playwright..."]
    try:
        page.goto(PREVISORA_LOGIN_URL, timeout=60000); logs.append("  Página cargada.")
        page.locator(f"#{PREVISORA_ID_TIPO_RECLAMANTE_LOGIN}").select_option(label=PREVISORA_TIPO_RECLAMANTE_LOGIN); logs.append("  - Tipo Reclamante OK.")
        page.locator(f"#{PREVISORA_ID_DOCUMENTO_LOGIN}").fill(PREVISORA_NO_DOCUMENTO_LOGIN); logs.append("  - Documento OK.")
        page.locator(PREVISORA_XPATH_BOTON_LOGIN).click(); logs.append("  - Clic en 'Iniciar Sesión'.")
        expect(page.locator(PREVISORA_XPATH_INICIO_LINK)).to_be_visible(timeout=30000); logs.append("Login exitoso.")
        return True, "\n".join(logs)
    except Exception: return False, "\n".join(logs)

def navegar_a_inicio(page: Page) -> tuple[bool, str]:
    # (Pega aquí tu función navegar_a_inicio() del previsora.py de glosas. Es idéntica)
    # ...
    logs = ["Navegando a la sección 'Inicio'..."]
    try:
        page.locator(PREVISORA_XPATH_INICIO_LINK).click()
        expect(page.locator(f"#{PREVISORA_ID_FACTURA_FORM}")).to_be_enabled(timeout=30000); logs.append("Navegación correcta.")
        return True, "\n".join(logs)
    except Exception: return False, "\n".join(logs)


# --- NUEVAS FUNCIONES ESPECIALIZADAS PARA FACTURACIÓN ---

def llenar_formulario_facturacion(page: Page, codigo_factura: str) -> tuple[str, str]:
    """Llena el formulario con los datos específicos para Facturación."""
    logs = [f"  Llenando formulario de Facturación (Factura: {codigo_factura})..."]
    try:
        # Llenar ciudad, factura, usuario y ramo (igual que en glosas)
        page.locator(f"//input[@id='{PREVISORA_ID_CIUDAD_HIDDEN_FORM}']/..").click()
        page.locator(PREVISORA_XPATH_CIUDAD_OPCION).click()
        page.locator(f"#{PREVISORA_ID_FACTURA_FORM}").fill(codigo_factura)
        page.locator(f"#{PREVISORA_ID_USUARIO_REGISTRA_FORM}").fill(PREVISORA_USUARIO_REGISTRA_FORM)
        page.locator(f"#{PREVISORA_ID_RAMO_FORM}").select_option(label=PREVISORA_RAMO_FORM)
        logs.append("    - Campos principales llenados.")
        
        # --- CAMBIOS CLAVE ---
        # 1. NO se llena el correo electrónico.
        # 2. Se selecciona "Factura presentada por primera vez" en Tipo de Cuenta.
        page.locator(f"#{PREVISORA_ID_TIPO_CUENTA_FORM}").select_option(value=PREVISORA_VALUE_TIPO_CUENTA_FACTURACION)
        logs.append("    - Tipo de Cuenta: Factura presentada por primera vez.")
        
        # 3. Se seleccionan los amparos
        page.locator(f"#{PREVISORA_ID_AMPAROS_FORM}").select_option(value=PREVISORA_VALUE_AMPARO_FORM)
        logs.append("    - Amparos OK.")
        
        return ESTADO_EXITO, "\n".join(logs)
    except Exception as e:
        # (código de manejo de errores)
        return ESTADO_FALLO, f"ERROR al llenar formulario: {e}"


def subir_archivos_facturacion(page: Page, documentos: dict[str, Path]) -> tuple[str, str]:
    """Sube los 4 archivos requeridos para la facturación."""
    logs = [f"  Subiendo {len(documentos)} archivos de facturación..."]
    try:
        # El sitio de Previsora usa el mismo input para todos los archivos "otros"
        # Los juntamos en una lista de rutas
        lista_de_rutas = [
            documentos["factura"],
            documentos["rips"],
            documentos["soportes"],
            documentos["anexos"],
        ]
        
        page.locator(f"#{PREVISORA_ID_INPUT_FILE_FORM}").set_input_files(lista_de_rutas)
        logs.append("    - 4 archivos adjuntados en el input.")

        # Los siguientes pasos son iguales a glosas (Enviar y confirmar pop-ups)
        page.locator(f"#{PREVISORA_ID_BOTON_ENVIAR_FORM}").click(); logs.append("    - Clic en 'Enviar'.")
        page.locator(PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR).click(timeout=15000); logs.append("    - Pop-up 'Sí, continuar' confirmado.")
        
        return ESTADO_EXITO, "\n".join(logs)
    except Exception as e:
        # (código de manejo de errores)
        return ESTADO_FALLO, f"ERROR al subir archivos: {e}"


def guardar_confirmacion_previsora(page: Page, output_folder: Path) -> tuple[str | None, str | None, str]:
    # Esta función puede ser idéntica a la de glosas. ¡La puedes pegar directamente!
    # ...
    try:
        page.locator(PREVISORA_XPATH_POPUP_CONTINUAR_GUARDAR).click(no_wait_after=True)
        popup_final = page.locator(PREVISORA_XPATH_FINAL_CONFIRMATION_POPUP_CONTAINER); expect(popup_final).to_be_visible(timeout=90000)
        # (resto de la función) ...
    except: return None, None, "ERROR..."
    return "path/to/RAD.pdf", "radicado_123", "Confirmación guardada"

# --- EL ORQUESTADOR PRINCIPAL PARA FACTURACIÓN ---

def procesar_carpeta(page: Page, subfolder_path: Path, subfolder_name: str) -> tuple[str, str | None, str | None, str]:
    """Función orquestadora para el proceso de Facturación de Previsora."""
    logs = [f"--- Iniciando Proceso de FACTURACIÓN (Previsora) para: '{subfolder_name}' ---"]
    try:
        # Filtrado de carpetas (reutilizamos la misma lógica)
        nombre_mayus = subfolder_name.upper()
        if any(palabra in nombre_mayus for palabra in PALABRAS_EXCLUSION_CARPETAS) or (subfolder_path / "RAD.pdf").is_file():
            logs.append("  OMITIENDO: Carpeta excluida o ya procesada.")
            return ESTADO_OMITIDO_RADICADO, None, None, "\n".join(logs)

        # 1. Llamar a la NUEVA función de búsqueda de documentos
        codigo_factura, documentos_paths, docs_log = encontrar_documentos_facturacion(subfolder_path, subfolder_name)
        logs.append(docs_log)
        if not (codigo_factura and documentos_paths):
            return ESTADO_FALLO, None, None, "\n".join(logs)
        
        # 2. Llenar el formulario específico de facturación
        estado_llenado, log_llenado = llenar_formulario_facturacion(page, codigo_factura)
        logs.append(log_llenado)
        if estado_llenado != ESTADO_EXITO:
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

        # 3. Subir los 4 archivos
        estado_subida, log_subida = subir_archivos_facturacion(page, documentos_paths)
        logs.append(log_subida)
        if estado_subida != ESTADO_EXITO:
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
            
        # 4. Guardar confirmación (función reutilizada)
        pdf_final_path, radicado_final, log_confirmacion = guardar_confirmacion_previsora(page, subfolder_path)
        logs.append(log_confirmacion)

        if pdf_final_path:
            return ESTADO_EXITO, radicado_final, codigo_factura, "\n".join(logs)
        else:
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

    except Exception as e:
        return ESTADO_FALLO, None, None, f"ERROR CRÍTICO en facturacion/previsora: {e}"