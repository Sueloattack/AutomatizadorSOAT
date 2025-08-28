# AutomatizadorSOAT/configuracion/constantes.py
"""
Archivo para almacenar constantes y configuración del automatizador.
"""

# --- Configuración General ---
APP_VERSION = "0.3"  # Puedes poner la versión de tu app

# --- Constantes Previsora ---
PREVISORA_ID = "previsora"  # Identificador interno
PREVISORA_NOMBRE = "Previsora"  # Nombre para mostrar en GUI
PREVISORA_LOGIN_URL = "https://soatapjuridica.consorcioprevisora.com/"
PREVISORA_TIPO_RECLAMANTE_LOGIN = "IPS"
PREVISORA_NO_DOCUMENTO_LOGIN = "8002098917"
PREVISORA_ID_TIPO_RECLAMANTE_LOGIN = "sl-tipo-reclamante"
PREVISORA_ID_DOCUMENTO_LOGIN = "txt-num-documento"
PREVISORA_XPATH_BOTON_LOGIN = "//button[contains(., 'Iniciar Sesión')]"
PREVISORA_XPATH_POPUP_LOGIN_ENTENDIDO = (
    "//button[contains(@class, 'swal2-confirm') and contains(text(), 'Entendido')]"
)

PREVISORA_XPATH_INICIO_LINK = "//a[contains(normalize-space(.), 'Inicio') and contains(@href, 'recepcion-reclamacion')]"
PREVISORA_ID_ELEMENTO_CLAVE_FORMULARIO = (
    "sl-ciudades"  # Usado para verificar que estamos en la página correcta
)

PREVISORA_CIUDAD_FORM_NOMBRE = "Ibagué"
PREVISORA_DATA_VALUE_CIUDAD = "73001"
PREVISORA_CORREO_FORM = "radicacionglosa@asotrauma.com.co"
PREVISORA_USUARIO_REGISTRA_FORM = "ASOTRAUMA"
PREVISORA_RAMO_FORM = "SOAT"
PREVISORA_VALUE_AMPARO_FORM = "1"
PREVISORA_VALUE_TIPO_CUENTA_FORM = "3"
PREVISORA_ID_CIUDAD_HIDDEN_FORM = "sl-ciudades"
PREVISORA_XPATH_CIUDAD_SEARCH_INPUT = f"//div[contains(@class, 'ui fluid search selection dropdown')][.//input[@id='{PREVISORA_ID_CIUDAD_HIDDEN_FORM}']]//input[contains(@class,'search')]"
PREVISORA_XPATH_CIUDAD_OPCION = f"//div[contains(@class, 'menu')]//div[contains(@class, 'item') and @data-value='{PREVISORA_DATA_VALUE_CIUDAD}']"
PREVISORA_ID_FACTURA_FORM = "txt-num-factura"
PREVISORA_ID_CORREO_FORM = "txt-email"
PREVISORA_ID_USUARIO_REGISTRA_FORM = "txt-usuario-registra"
PREVISORA_ID_RAMO_FORM = "sl-ramo"
PREVISORA_ID_AMPAROS_FORM = "sl-tipo-amparo"
PREVISORA_ID_TIPO_CUENTA_FORM = "sl-tipo-cuenta"
PREVISORA_XPATH_POPUP_FACTURA_CONTINUAR = "//div[contains(@class, 'jconfirm') and contains(@class, 'jconfirm-open')]//button[contains(@class, 'btn-green') and normalize-space(text())='CONTINUAR']"

PREVISORA_ID_INPUT_FILE_FORM = "str_bytes_archivo_otros"
PREVISORA_ID_BOTON_ENVIAR_FORM = "btn-enviar-datos2y3"
PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR = "//div[contains(@class, 'jconfirm') and contains(@class, 'jconfirm-open')]//button[contains(@class, 'btn-green') and normalize-space(text())='Sí, continuar']"
PREVISORA_XPATH_POPUP_CONTINUAR_GUARDAR = "//div[contains(@class, 'jconfirm') and contains(@class, 'jconfirm-open')]//button[contains(@class, 'btn-green') and contains(translate(normalize-space(text()), 'CG', 'cg'), 'continuar y guardar')]"

PREVISORA_XPATH_FINAL_CONFIRMATION_POPUP_CONTAINER = "//div[contains(@class, 'jconfirm-open')]//div[contains(@class, 'jconfirm-box') and contains(@class, 'jconfirm-type-green')][.//span[contains(@class,'jconfirm-title')]//b[contains(text(),'Registro Generado')]]"
PREVISORA_XPATH_BOTON_NUEVA_RECLAMACION = "//div[contains(@class, 'jconfirm-open')]//button[contains(@class, 'btn-green') and normalize-space(text())='Generar una nueva reclamación']"

PREVISORA_REDUCED_SLEEP_POST_UPLOAD = 0.1
PREVISORA_NOMBRE_EN_PDF = "LA PREVISORA S.A."
PREVISORA_VALUE_TIPO_CUENTA_FACTURACION = "1"
# --- Constantes Mundial (Ejemplo Futuro) ---
MUNDIAL_ID = "mundial"
MUNDIAL_NOMBRE = "Seguros Mundial"
# MUNDIAL_LOGIN_URL = "..."
# ... otras constantes para Mundial

# --- Constantes AXA (Ejemplo Futuro) ---
AXASOAT_ID = "axa_soat"
AXASOAT_NOMBRE = "AXA Colpatria SOAT"
AXASOAT_LOGIN_URL = "https://axa.claimonline.com.co/"
# Nombre a buscar en el PDF de la carta glosa para la validación universal
AXASOAT_NOMBRE_EN_PDF = "AXA COLPATRIA SEGUROS S.A."

# Datos de Login
AXASOAT_TIPO_RECLAMANTE_LOGIN = "IPS"
AXASOAT_DOCUMENTO_LOGIN = "8002098917"

# Selectores 
AXASOAT_SELECTOR_TIPO_RECLAMANTE = "select[selector='tipo_cuenta_select_selector']"
AXASOAT_SELECTOR_DOCUMENTO = "input[selector='nit_selector']"
AXASOAT_SELECTOR_BOTON_LOGIN = "button[selector='Login_button_selector']"

# Selector para el botón "Aceptar" del pop-up/modal de notificación
AXASOAT_SELECTOR_MODAL_ACEPTAR = "button:has-text('Aceptar')"

# Selector clave para verificar que estamos en la página del formulario
# Este es el input del NIT Ramo que mencionaste.
AXASOAT_SELECTOR_FORMULARIO_VERIFY = "input[selector='nitramo_selector']"

# Datos y selectores para el formulario de radicación
AXASOAT_NIT_RAMO_FORM = "8600021846"
AXASOAT_TIPO_CUENTA_FORM_RESPUESTA_OBJECION = "Respuesta a una objeción"

AXASOAT_SELECTOR_NIT_RAMO = "input[selector='nitramo_selector']"
AXASOAT_SELECTOR_TIPO_CUENTA = "select[selector='tipo_cuenta_select_selector']" # Coincide con el de login, pero es de otra página
AXASOAT_SELECTOR_FECHA_ATENCION = "input[selector='fecha_atencion_date_selector']"

AXASOAT_SELECTOR_NUMERO_FACTURA = "input[selector='numero_factura_input_selector']"
AXASOAT_SELECTOR_MODAL_FACTURA_ACEPTAR = "button[selector='Aceptar_button_selector']"

AXASOAT_SELECTOR_CHECKBOX_RIPS = "input[name='check_service']"

# Datos y selector para el Correo Electrónico
AXASOAT_CORREO_FORM = "radicacionglosa@asotrauma.com.co"
AXASOAT_SELECTOR_CORREO = "input[selector='email_input_selector']"

# Datos y selector para el Usuario que Registra
AXASOAT_USUARIO_REGISTRA_FORM = "DIANA CAROLINA GIRALDO"
AXASOAT_SELECTOR_USUARIO_REGISTRA = "input[name='usuario_registro']"
AXASOAT_SELECTOR_INPUT_FILE = "input[name='otros']"

AXASOAT_SELECTOR_SERVER_ERROR_H1 = "h1:has-text('502 Bad Gateway')"

# Selector para el "100%" que confirma la subida del archivo
AXASOAT_SELECTOR_UPLOAD_COMPLETE = "span:has-text('100%')"

# Selector para el botón "Enviar"
AXASOAT_SELECTOR_BOTON_ENVIAR = "button[selector='Enviar_button_selector']"
AXASOAT_SELECTOR_MODAL_POST_UPLOAD_ACEPTAR = "div:has-text('¿Desea Continuar?') >> button[selector='Aceptar_button_selector']"

# Selector para el párrafo del modal final que contiene el radicado
AXASOAT_SELECTOR_MODAL_FINAL_TEXTO = "p:has-text('reclamacion registrada correctamente')"

# Selector para el botón final de "Aceptar"
AXASOAT_SELECTOR_MODAL_FINAL_ACEPTAR = "div.bg-neutral-50 button[selector='Aceptar_button_selector']"

EMAIL_IMAP_SERVER = "imap.gmail.com"  # Servidor IMAP (ej. para Gmail)
EMAIL_USER_ADDRESS = "radicacionglosa@asotrauma.com.co" # El correo donde llegan los soportes
# Para Gmail, usa una "Contraseña de aplicación", no tu contraseña normal.
# Búscalo en la configuración de seguridad de tu cuenta de Google.
EMAIL_APP_PASSWORD = "yuzy hkzu rnsi vggx"
# Remitente específico de los correos de radicación de AXA
AXASOAT_EMAIL_SENDER = "notificaciones@claimonline.com.co"
# --- IDs INTERNOS PARA LAS ÁREAS ---
AREA_GLOSAS_ID = "glosas"
AREA_FACTURACION_ID = "facturacion"
EMAIL_PROCESSED_FOLDER = "Procesados" 
EMAIL_SEARCH_RETRIES = 60    # Número de veces que se reintentará
EMAIL_SEARCH_DELAY_SECONDS = 15 
# --- CONFIGURACIÓN CENTRALIZADA POR ÁREA ---
# Esto ahora es un diccionario. La clave es el ID del área.
# El valor es la lista de aseguradoras disponibles para esa área.
CONFIGURACION_AREAS = {
    AREA_GLOSAS_ID: [
        (PREVISORA_NOMBRE, PREVISORA_ID),
        (MUNDIAL_NOMBRE, MUNDIAL_ID),
        (AXASOAT_NOMBRE, AXASOAT_ID),
    ],
    AREA_FACTURACION_ID: [
        # Quizás facturación solo está disponible para Previsora por ahora
        (PREVISORA_NOMBRE, PREVISORA_ID),
    ]
}

# --- Configuración de Procesamiento de Carpetas ---
# Palabras clave en nombres de carpetas que causarán que se omitan. No distingue mayúsculas/minúsculas.
PALABRAS_EXCLUSION_CARPETAS = [
    "NO RADICAR",
    "CARTERA",
    # "CERO EN CARTERA" se cubre con "CARTERA"
]
