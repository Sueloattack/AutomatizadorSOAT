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

# --- Constantes Mundial (Ejemplo Futuro) ---
MUNDIAL_ID = "mundial"
MUNDIAL_NOMBRE = "Seguros Mundial"
# MUNDIAL_LOGIN_URL = "..."
# ... otras constantes para Mundial

# --- Constantes AXA (Ejemplo Futuro) ---
AXA_ID = "axa"
AXA_NOMBRE = "AXA Colpatria"
# AXA_LOGIN_URL = "..."
# ... otras constantes para AXA

# --- Mapeo de Aseguradoras para la GUI ---
# (ID_INTERNO, NOMBRE_MOSTRAR)
# Esto facilita añadir nuevas aseguradoras al ComboBox
ASEGURADORAS_CONFIG = [
    (PREVISORA_NOMBRE, PREVISORA_ID),
    (MUNDIAL_NOMBRE, MUNDIAL_ID),
    (AXA_NOMBRE, AXA_ID),
]
