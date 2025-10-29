"""
Archivo centralizado para todas las constantes y configuraciones de la aplicación.

La estructura de este archivo es la siguiente:
1.  CONFIGURACIÓN GENERAL DE LA APLICACIÓN: Versión, IDs de áreas.
2.  CONSTANTES POR ASEGURADORA: El bloque más grande, subdividido para cada aseguradora.
3.  CONFIGURACIÓN DE LÓGICA DE NEGOCIO: Reglas que no son de UI ni de una aseguradora específica.
4.  MAPEO E INTEGRACIÓN DE LA APLICACIÓN: Diccionarios y listas que unen todo para la UI.
"""

# ==============================================================================
# 1. CONFIGURACIÓN GENERAL DE LA APLICACIÓN
# ==============================================================================

APP_VERSION = "0.3"

# --- IDs Internos para las Áreas de Negocio ---
# Usados en la UI y para la carga dinámica de módulos de automatización.
AREA_GLOSAS_ID = "glosas"
AREA_FACTURACION_ID = "facturacion"

#API de GEMA
MUNDIAL_ESCOLAR_API_BASE_URL = 'https://asotrauma.ngrok.app/api-busqueda-gema/public/api'


# ==============================================================================
# 2. CONSTANTES POR ASEGURADORA
# ==============================================================================

# ------------------------------------------------------------------------------
# --- PREVISORA ---
# ------------------------------------------------------------------------------

# --- Identificadores Generales (Previsora) ---
PREVISORA_ID = "previsora"
PREVISORA_NOMBRE = "Previsora"
PREVISORA_NOMBRE_EN_PDF = "LA PREVISORA S.A."
PREVISORA_MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

# --- Página de Login (Previsora) ---
PREVISORA_LOGIN_URL = "https://soatapjuridica.consorcioprevisora.com/"
PREVISORA_TIPO_RECLAMANTE_LOGIN = "IPS"
PREVISORA_NO_DOCUMENTO_LOGIN = "8002098917"
PREVISORA_ID_TIPO_RECLAMANTE_LOGIN = "sl-tipo-reclamante"
PREVISORA_ID_DOCUMENTO_LOGIN = "txt-num-documento"
PREVISORA_XPATH_BOTON_LOGIN = "//button[contains(., 'Iniciar Sesión')]"
PREVISORA_XPATH_POPUP_LOGIN_ENTENDIDO = "//button[contains(@class, 'swal2-confirm') and contains(text(), 'Entendido')]"

# --- Navegación y Formulario de GLOSAS (Previsora) ---
PREVISORA_XPATH_INICIO_LINK = "//a[contains(normalize-space(.), 'Inicio') and contains(@href, 'recepcion-reclamacion')]"
PREVISORA_ID_ELEMENTO_CLAVE_FORMULARIO = "sl-ciudades"  # Usado para verificar la carga de página
PREVISORA_CIUDAD_FORM_NOMBRE = "Ibagué"
PREVISORA_DATA_VALUE_CIUDAD = "73001"
PREVISORA_CORREO_FORM = "radicacionglosa@asotrauma.com.co"
PREVISORA_USUARIO_REGISTRA_FORM = "ASOTRAUMA"
PREVISORA_RAMO_FORM = "SOAT"
PREVISORA_VALUE_AMPARO_FORM = "1"
PREVISORA_VALUE_TIPO_CUENTA_FORM = "3"  # "Respuesta Glosa u Objeción"

# --- Selectores de Formulario de GLOSAS (Previsora) ---
PREVISORA_ID_CIUDAD_HIDDEN_FORM = "sl-ciudades"
PREVISORA_XPATH_CIUDAD_SEARCH_INPUT = f"//div[contains(@class, 'ui fluid search selection dropdown')][.//input[@id='{PREVISORA_ID_CIUDAD_HIDDEN_FORM}']]//input[contains(@class,'search')]"
PREVISORA_XPATH_CIUDAD_OPCION = f"//div[contains(@class, 'menu')]//div[contains(@class, 'item') and @data-value='{PREVISORA_DATA_VALUE_CIUDAD}']"
PREVISORA_ID_FACTURA_FORM = "txt-num-factura"
PREVISORA_ID_CORREO_FORM = "txt-email"
PREVISORA_ID_USUARIO_REGISTRA_FORM = "txt-usuario-registra"
PREVISORA_ID_RAMO_FORM = "sl-ramo"
PREVISORA_ID_AMPAROS_FORM = "sl-tipo-amparo"
PREVISORA_ID_TIPO_CUENTA_FORM = "sl-tipo-cuenta"

# --- Subida y Envío de Formulario de GLOSAS (Previsora) ---
PREVISORA_ID_INPUT_FILE_FORM = "str_bytes_archivo_otros"
PREVISORA_ID_BOTON_ENVIAR_FORM = "btn-enviar-datos2y3"
PREVISORA_XPATH_POPUP_FACTURA_CONTINUAR = "//div[contains(@class, 'jconfirm') and contains(@class, 'jconfirm-open')]//button[contains(@class, 'btn-green') and normalize-space(text())='CONTINUAR']"
PREVISORA_XPATH_POPUP_FACTURA_CONTINUAR_GUARDAR = "//div[contains(@class, 'jconfirm-buttons')]//button[contains(text(), 'Continuar y Guardar')]"
PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR = "//div[contains(@class, 'jconfirm') and contains(@class, 'jconfirm-open')]//button[contains(@class, 'btn-green') and normalize-space(text())='Sí, continuar']"
PREVISORA_XPATH_POPUP_CONTINUAR_GUARDAR = "//div[contains(@class, 'jconfirm') and contains(@class, 'jconfirm-open')]//button[contains(@class, 'btn-green') and contains(translate(normalize-space(text()), 'CG', 'cg'), 'continuar y guardar')]"
PREVISORA_XPATH_FINAL_CONFIRMATION_POPUP_CONTAINER = "//div[contains(@class, 'jconfirm-open')]//div[contains(@class, 'jconfirm-box') and contains(@class, 'jconfirm-type-green')][.//span[contains(@class,'jconfirm-title')]//b[contains(text(),'Registro Generado')]]"
PREVISORA_XPATH_BOTON_NUEVA_RECLAMACION = "//div[contains(@class, 'jconfirm-open')]//button[contains(@class, 'btn-green') and normalize-space(text())='Generar una nueva reclamación']"

# --- Sub-sección: Selectores para FACTURACIÓN (Previsora) ---
PREVISORA_VALUE_TIPO_CUENTA_FACTURACION = "1"  # "Factura presentada por primera vez"
PREVISORA_ID_INPUT_FURIPS = "str_bytes_archivo_furips"
PREVISORA_ID_INPUT_FACTURA = "str_bytes_archivo_factura"
PREVISORA_ID_INPUT_HC = "f-archivo-historia-clinica"
PREVISORA_ID_INPUT_SOPORTES_HC = "str_bytes_soporte_historia_clinica"
PREVISORA_ID_BOTON_ENVIAR_FACTURACION = "btn_enviar_datos1"

# --- Misceláneos (Previsora) ---
PREVISORA_REDUCED_SLEEP_POST_UPLOAD = 0.1


# ------------------------------------------------------------------------------
# --- SEGUROS MUNDIAL ---
# ------------------------------------------------------------------------------
MUNDIAL_ID = "mundial"
MUNDIAL_NOMBRE = "Seguros Mundial"


# ------------------------------------------------------------------------------
# --- MUNDIAL ESCOLAR ---
# ------------------------------------------------------------------------------
MUNDIAL_ESCOLAR_ID = "mundial_escolar"
MUNDIAL_ESCOLAR_NOMBRE = "Mundial Escolar"
MUNDIAL_ESCOLAR_URL = "https://www.activa-it.net/Login.aspx"
MUNDIAL_ESCOLAR_SEDE1_USER = "MUN730010082601"
MUNDIAL_ESCOLAR_SEDE1_PASS = "Agosto2025*"
MUNDIAL_ESCOLAR_SEDE2_USER = "MUN730010082602"
MUNDIAL_ESCOLAR_SEDE2_PASS = "Asotrauma-2025="


# ------------------------------------------------------------------------------
# --- AXA COLPATRIA SOAT ---
# ------------------------------------------------------------------------------

# --- Identificadores Generales (AXA) ---
AXASOAT_ID = "axa_soat"
AXASOAT_NOMBRE = "AXA Colpatria SOAT"
AXASOAT_NOMBRE_EN_PDF = "AXA COLPATRIA SEGUROS S.A."

# --- Página de Login (AXA) ---
AXASOAT_LOGIN_URL = "https://axa.claimonline.com.co/"
AXASOAT_TIPO_RECLAMANTE_LOGIN = "IPS"
AXASOAT_DOCUMENTO_LOGIN = "8002098917"
AXASOAT_SELECTOR_TIPO_RECLAMANTE = "select[selector='tipo_cuenta_select_selector']"
AXASOAT_SELECTOR_DOCUMENTO = "input[selector='nit_selector']"
AXASOAT_SELECTOR_BOTON_LOGIN = "button[selector='Login_button_selector']"
AXASOAT_SELECTOR_MODAL_ACEPTAR = "button:has-text('Aceptar')"

# --- Formulario de Radicación (AXA) ---
AXASOAT_SELECTOR_FORMULARIO_VERIFY = "input[selector='nitramo_selector']"  # Elemento clave para verificar carga
AXASOAT_NIT_RAMO_FORM = "8600021846"
AXASOAT_TIPO_CUENTA_FORM_RESPUESTA_OBJECION = "Respuesta a una objeción"
AXASOAT_CORREO_FORM = "radicacionglosa@asotrauma.com.co"
AXASOAT_USUARIO_REGISTRA_FORM = "DIANA CAROLINA GIRALDO"
AXASOAT_SELECTOR_NIT_RAMO = "input[selector='nitramo_selector']"
AXASOAT_SELECTOR_TIPO_CUENTA = "select[selector='tipo_cuenta_select_selector']"
AXASOAT_SELECTOR_FECHA_ATENCION = "input[selector='fecha_atencion_date_selector']"
AXASOAT_SELECTOR_NUMERO_FACTURA = "input[selector='numero_factura_input_selector']"
AXASOAT_SELECTOR_CORREO = "input[selector='email_input_selector']"
AXASOAT_SELECTOR_USUARIO_REGISTRA = "input[name='usuario_registro']"

# --- Subida y Envío de Formulario (AXA) ---
AXASOAT_SELECTOR_CHECKBOX_RIPS = "input[name='check_service']"
AXASOAT_SELECTOR_INPUT_FILE = "input[name='otros']"
AXASOAT_SELECTOR_BOTON_ENVIAR = "button[selector='Enviar_button_selector']"
AXASOAT_SELECTOR_UPLOAD_COMPLETE = "span:has-text('100%')"

# --- Pop-ups y Modales (AXA) ---
AXASOAT_SELECTOR_MODAL_FACTURA_ACEPTAR = "button[selector='Aceptar_button_selector']"
AXASOAT_SELECTOR_MODAL_POST_UPLOAD_ACEPTAR = "div:has-text('¿Desea Continuar?') >> button[selector='Aceptar_button_selector']"
AXASOAT_SELECTOR_MODAL_FINAL_TEXTO = "p:has-text('reclamacion registrada correctamente')"
AXASOAT_SELECTOR_MODAL_FINAL_ACEPTAR = "div:has-text('reclamacion registrada correctamente') >> button[selector='Aceptar_button_selector']"
AXASOAT_TIPO_CUENTA_FORM_FACTURACION = "Factura presentada por primera vez"
AXASOAT_CORREO_FACTURACION = "facturacion@asotrauma.com.co"           
AXASOAT_USUARIO_REGISTRA_FACTURACION = "clinica asotrauma"             
AXASOAT_SELECTOR_CUV_INPUT = "input[name='cuv_text']"     
AXASOAT_SELECTOR_MODAL_FACTURA_RECIBIDA_ACEPTAR = "div:has-text('fue recibida el dia') >> button:has-text('Aceptar')"

AXASOAT_SELECTOR_INPUT_FURIPS_FILE = "input[name='furips']"
AXASOAT_SELECTOR_INPUT_FACTURA_FILE = "input[name='factura']"
AXASOAT_SELECTOR_INPUT_HC_FILE = "input[name='historia_clinica']"
AXASOAT_SELECTOR_INPUT_RIPS_JSON = "input[name='rips']"  
AXASOAT_SELECTOR_INPUT_FEV_XML = "input[name='fev']" 

# --- Selectores de Error (AXA) ---
AXASOAT_SELECTOR_SERVER_ERROR_H1 = "h1:has-text('502 Bad Gateway')"



# ==============================================================================
# 3. CONFIGURACIÓN DE LÓGICA DE NEGOCIO Y CARACTERÍSTICAS
# ==============================================================================

# --- Configuración del Lector de Correos (Email Listener) ---
EMAIL_IMAP_SERVER = "imap.gmail.com"
EMAIL_USER_ADDRESS = "radicacionglosa@asotrauma.com.co"
EMAIL_APP_PASSWORD = "yuzy hkzu rnsi vggx"  # Contraseña de aplicación
EMAIL_PROCESSED_FOLDER = "Procesados"
EMAIL_SEARCH_RETRIES = 60
EMAIL_SEARCH_DELAY_SECONDS = 15
# Remitente específico del que se esperan correos para asociar con la automatización.
AXASOAT_EMAIL_SENDER = "notificaciones@claimonline.com.co"

# --- Configuración del Procesamiento de Carpetas ---
# Carpetas que contengan estas palabras clave serán ignoradas por el automatizador.
PALABRAS_EXCLUSION_CARPETAS = [
    "NO RADICAR",
    "CARTERA",
]


# ==============================================================================
# 4. MAPEO E INTEGRACIÓN DE LA APLICACIÓN
# ==============================================================================
# Esta sección une las constantes definidas arriba para ser usadas por la aplicación,
# principalmente por la Interfaz de Usuario y el Trabajador.

# --- Configuración Centralizada por Área para la UI ---
# Define qué aseguradoras están disponibles en cada área del negocio.
CONFIGURACION_AREAS = {
    AREA_GLOSAS_ID: [
        (PREVISORA_NOMBRE, PREVISORA_ID),
        (MUNDIAL_NOMBRE, MUNDIAL_ID),
        (AXASOAT_NOMBRE, AXASOAT_ID),
        (MUNDIAL_ESCOLAR_NOMBRE, MUNDIAL_ESCOLAR_ID),
    ],
    AREA_FACTURACION_ID: [
        (PREVISORA_NOMBRE, PREVISORA_ID),
        (AXASOAT_NOMBRE, AXASOAT_ID),
    ]
}

# --- Listas de Comportamiento Especial por Aseguradora ---
# Define qué aseguradoras requieren que se active el lector de correos.
ASEGURADORAS_CON_EMAIL_LISTENER = [
    AXASOAT_ID,
]