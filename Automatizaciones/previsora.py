# AutomatizadorSOAT/automatizaciones/previsora.py
"""
Lógica de automatización específica para la plataforma Previsora SOAT.
"""
import time
import traceback
from pathlib import Path
import re  # Necesario para extraer el código con regex

# Importaciones Selenium/Pillow/Constantes...
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException,
    NoSuchElementException,
)
from selenium.webdriver.common.keys import Keys

try:
    from PIL import Image
except ImportError:
    print("ERROR CRITICO: Falta Pillow. pip install Pillow")
    raise

try:
    # Importar constantes (USANDO NOMBRES DE CARPETA EN MINÚSCULAS)
    from Configuracion.constantes import (
        PREVISORA_LOGIN_URL,
        PREVISORA_TIPO_RECLAMANTE_LOGIN,
        PREVISORA_NO_DOCUMENTO_LOGIN,
        PREVISORA_ID_TIPO_RECLAMANTE_LOGIN,
        PREVISORA_ID_DOCUMENTO_LOGIN,
        PREVISORA_XPATH_BOTON_LOGIN,
        PREVISORA_XPATH_POPUP_LOGIN_ENTENDIDO,
        PREVISORA_XPATH_INICIO_LINK,
        PREVISORA_ID_ELEMENTO_CLAVE_FORMULARIO,
        PREVISORA_CIUDAD_FORM_NOMBRE,
        PREVISORA_XPATH_CIUDAD_OPCION,
        PREVISORA_ID_FACTURA_FORM,
        PREVISORA_CORREO_FORM,
        PREVISORA_USUARIO_REGISTRA_FORM,
        PREVISORA_RAMO_FORM,
        PREVISORA_ID_CORREO_FORM,
        PREVISORA_ID_USUARIO_REGISTRA_FORM,
        PREVISORA_ID_RAMO_FORM,
        PREVISORA_XPATH_POPUP_FACTURA_CONTINUAR,
        PREVISORA_ID_AMPAROS_FORM,
        PREVISORA_VALUE_AMPARO_FORM,
        PREVISORA_ID_TIPO_CUENTA_FORM,
        PREVISORA_VALUE_TIPO_CUENTA_FORM,
        PREVISORA_ID_INPUT_FILE_FORM,
        PREVISORA_ID_BOTON_ENVIAR_FORM,
        PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR,
        PREVISORA_XPATH_POPUP_CONTINUAR_GUARDAR,
        PREVISORA_XPATH_FINAL_CONFIRMATION_POPUP_CONTAINER,
        PREVISORA_XPATH_BOTON_NUEVA_RECLAMACION,
        PREVISORA_REDUCED_SLEEP_POST_UPLOAD,
        PREVISORA_ID_CIUDAD_HIDDEN_FORM,
    )
except ImportError as e:
    print(
        f"ERROR CRITICO: No se pudieron importar constantes desde 'configuracion.constantes': {e}"
    )
    raise  # Relanzar para detener ejecución si falta configuración

# --- Estados de Retorno ---
ESTADO_EXITO = "EXITO"
ESTADO_FALLO = "FALLO"
ESTADO_OMITIDO_RADICADO = "OMITIDO_RADICADO"
ESTADO_OMITIDO_DUPLICADA = "OMITIDO_DUPLICADA"
# ESTADO_FALLO = 'SESION_EXPIRADA'

# --- Funciones Auxiliares Específicas de Previsora (si las hay) ---


def _handle_popup_previsora(
    driver,
    wait,
    wait_time,
    popup_container_xpath,
    button_xpath,
    popup_name="Pop-up Previsora",
) -> tuple[bool, str]:
    """
    Intenta detectar y cerrar un pop-up específico de Previsora.
    Retorna (True/False si se intentó manejar, logs).
    """
    log_messages = []
    try:
        popup_wait = WebDriverWait(driver, wait_time)
        log_messages.append(f"  Verificando {popup_name} (max {wait_time}s)...")
        # Esperar visibilidad del contenedor
        popup_wait.until(
            EC.visibility_of_element_located((By.XPATH, popup_container_xpath))
        )
        # Esperar que el botón específico sea clickable
        button_to_click = popup_wait.until(
            EC.element_to_be_clickable((By.XPATH, button_xpath))
        )
        log_messages.append(f"    {popup_name} encontrado. Intentando hacer clic...")

        intentos = 0
        max_intentos = 3
        click_exitoso = False
        while intentos < max_intentos:
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView(true);", button_to_click
                )
                # Pausa mínima para asegurar que el scroll termine antes del clic JS
                time.sleep(0.1)
                driver.execute_script("arguments[0].click();", button_to_click)
                log_messages.append(
                    f"    Clic {popup_name} (intento {intentos + 1}) OK."
                )
                # Esperar un breve momento para que el DOM reaccione
                time.sleep(0.5)
                log_messages.append(f"    {popup_name} cerrado/ignorado.")
                click_exitoso = True
                break
            except Exception as e_click:
                intentos += 1
                log_messages.append(
                    f"    Intento {intentos} clic {popup_name} falló: {str(e_click)[:100]}..."
                )
                time.sleep(0.5)

        if not click_exitoso:
            log_messages.append(
                f"    ADVERTENCIA: No se pudo confirmar cierre de {popup_name}."
            )
        return True, "\n".join(log_messages)  # Se intentó manejar

    except TimeoutException:
        log_messages.append(f"    {popup_name} no detectado.")
        return False, "\n".join(log_messages)  # No apareció, no es un error de manejo
    except Exception as e_popup:
        log_messages.append(f"    Error manejando {popup_name}: {e_popup}")
        traceback.print_exc()
        return False, "\n".join(log_messages)  # Falló el manejo


# --- Funciones Principales de Automatización para Previsora ---


def login_previsora(driver, wait) -> tuple[bool, str]:
    """Realiza el proceso de login en Previsora. Retorna (exito, logs)."""
    logs = ["Iniciando login en Previsora..."]
    try:
        logs.append(f"  Navegando a {PREVISORA_LOGIN_URL}...")
        driver.get(PREVISORA_LOGIN_URL)
        logs.append("  Página cargada.")

        logs.append(
            f"  Seleccionando Tipo Reclamante '{PREVISORA_TIPO_RECLAMANTE_LOGIN}'..."
        )
        select_tipo = Select(
            wait.until(
                EC.element_to_be_clickable((By.ID, PREVISORA_ID_TIPO_RECLAMANTE_LOGIN))
            )
        )
        select_tipo.select_by_visible_text(PREVISORA_TIPO_RECLAMANTE_LOGIN)
        logs.append("  - Tipo Reclamante OK.")

        # Manejar pop-up inicial 'Entendido'
        popup_handled, popup_log = _handle_popup_previsora(
            driver,
            wait,
            5,
            "//div[contains(@class, 'swal2-popup') and contains(@class, 'swal2-show')]",
            PREVISORA_XPATH_POPUP_LOGIN_ENTENDIDO,
            "Pop-up 'Entendido' inicial",
        )
        logs.append(popup_log)

        logs.append(f"  Ingresando Documento '{PREVISORA_NO_DOCUMENTO_LOGIN}'...")
        input_documento = wait.until(
            EC.visibility_of_element_located((By.ID, PREVISORA_ID_DOCUMENTO_LOGIN))
        )
        input_documento.clear()
        input_documento.send_keys(PREVISORA_NO_DOCUMENTO_LOGIN)
        logs.append("  - Documento OK.")

        logs.append("  Clic 'Iniciar Sesión'...")
        boton_ingresar = wait.until(
            EC.element_to_be_clickable((By.XPATH, PREVISORA_XPATH_BOTON_LOGIN))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", boton_ingresar)
        time.sleep(0.1)  # Pausa mínima post-scroll
        driver.execute_script("arguments[0].click();", boton_ingresar)
        logs.append("  Login enviado.")

        # Esperar a que cargue la siguiente página (verificar elemento clave como el link Inicio)
        wait.until(
            EC.presence_of_element_located((By.XPATH, PREVISORA_XPATH_INICIO_LINK))
        )
        logs.append("Login exitoso, página principal cargada.")
        return True, "\n".join(logs)

    except (
        TimeoutException,
        NoSuchElementException,
        ElementClickInterceptedException,
    ) as e:
        error_msg = f"ERROR durante el login en Previsora: {type(e).__name__} - {e}"
        logs.append(error_msg)
        traceback.print_exc()  # Para depuración interna
        return False, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado durante el login en Previsora: {e}"
        logs.append(error_msg)
        traceback.print_exc()
        return False, "\n".join(logs)


def navegar_a_inicio_previsora(driver, wait) -> tuple[bool, str]:
    """
    Navega a la sección 'Inicio' (Recepción Reclamación) si no está ya allí.
    Espera la URL correcta y luego la interactividad de un campo clave.
    Retorna (True/False exito, logs).
    """
    logs = ["Verificando/Navegando a sección 'Inicio' (Recepción Reclamación)..."]
    url_objetivo = (
        "/reclamacion/recepcion-reclamacion"  # URL esperada (ajusta si es diferente)
    )
    id_campo_clave_interactivo = (
        PREVISORA_ID_FACTURA_FORM  # Esperar que el input de factura esté listo
    )

    try:
        # 1. Verificar si YA estamos en la URL correcta (rápido)
        current_url = driver.current_url
        logs.append(f"  URL actual: {current_url}")
        if url_objetivo in current_url:
            logs.append("  -> Ya estábamos en la URL del formulario.")
            # Verificar rápidamente si el campo clave ya está listo
            try:
                WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.ID, id_campo_clave_interactivo))
                )
                logs.append("  -> Página y campo clave ya listos.")
                return True, "\n".join(logs)
            except TimeoutException:
                logs.append(
                    "  -> En URL correcta, pero campo clave no listo aún. Procediendo con espera..."
                )
                # Continuar abajo para esperar el campo clave con más tiempo
        else:
            logs.append(
                "  -> No estamos en la URL del formulario. Procediendo a navegar..."
            )

        # 2. Intentar hacer clic en 'Inicio' y esperar URL + Campo
        # Usar el wait principal (35s) aquí, ya que el clic podría fallar
        max_nav_attempts = 2  # Reintentos para el clic en 'Inicio'
        nav_click_ok = False
        for attempt in range(max_nav_attempts):
            try:
                logs.append(
                    f"  Intento Navegación {attempt + 1}/{max_nav_attempts}: Clic en enlace 'Inicio'..."
                )
                link_inicio = wait.until(
                    EC.element_to_be_clickable((By.XPATH, PREVISORA_XPATH_INICIO_LINK))
                )
                driver.execute_script("arguments[0].click();", link_inicio)
                logs.append("    Clic OK.")
                nav_click_ok = True
                break  # Salir del bucle de clic si tiene éxito
            except (
                TimeoutException,
                NoSuchElementException,
                ElementClickInterceptedException,
            ) as e_click:
                logs.append(
                    f"    ERROR Intento {attempt + 1} al hacer clic en 'Inicio': {type(e_click).__name__}"
                )
                if attempt == max_nav_attempts - 1:
                    logs.append(
                        "    FALLO CRÍTICO: No se pudo hacer clic en 'Inicio' tras reintentos."
                    )
                    return False, "\n".join(logs)  # Fallar si el clic no funciona
                logs.append("    Reintentando clic tras pausa...")
                time.sleep(1)

        if not nav_click_ok:  # Si el bucle termina sin éxito en el clic
            return False, "\n".join(logs)

        # 3. Esperar a que la URL cambie Y que el campo clave sea interactuable
        try:
            logs.append(
                f"    Esperando cambio a URL que contenga '{url_objetivo}' (Max {wait._timeout}s)..."
            )
            wait.until(EC.url_contains(url_objetivo))
            logs.append(f"    URL correcta alcanzada: {driver.current_url}")

            logs.append(
                f"    Esperando que campo '{id_campo_clave_interactivo}' sea interactuable (Max {wait._timeout}s)..."
            )
            wait.until(EC.element_to_be_clickable((By.ID, id_campo_clave_interactivo)))
            logs.append("    Página y campo clave listos para llenado.")
            return True, "\n".join(logs)  # Éxito final

        except TimeoutException as e_wait_final:
            current_url_after_wait = (
                driver.current_url
            )  # Obtener URL al fallar la espera
            logs.append(
                f"    ERROR: Timeout esperando URL '{url_objetivo}' o campo '{id_campo_clave_interactivo}'."
            )
            logs.append(f"      URL al fallar la espera: {current_url_after_wait}")
            traceback.print_exc()
            return False, "\n".join(logs)  # Fallo

    except Exception as e_general:
        error_msg = f"ERROR general en navegar_a_inicio_previsora: {e_general}"
        logs.append(error_msg)
        traceback.print_exc()
        return False, "\n".join(logs)


def llenar_formulario_previsora(driver, wait, codigo_factura) -> tuple[str, str]:
    """
    Llena los campos del formulario principal.
    Retorna (estado, logs):
        - 'EXITO': Si se llenó correctamente.
        - 'FALLO': Si hubo un error durante el llenado.
        - 'FACTURA_DUPLICADA': Si apareció el pop-up de factura duplicada/existente.
    """
    logs = [f"  Llenando formulario principal (Factura: {codigo_factura})..."]
    estado_final = "FALLO"
    try:
        # Seleccionar Ciudad
        logs.append(f"    Seleccionando Ciudad '{PREVISORA_CIUDAD_FORM_NOMBRE}'...")
        try:
            opcion_ciudad = wait.until(
                EC.element_to_be_clickable((By.XPATH, PREVISORA_XPATH_CIUDAD_OPCION))
            )
            opcion_ciudad.click()
        except TimeoutException:
            logs.append(
                "      (Opción ciudad no visible, intentando abrir dropdown...)"
            )
            dropdown_container_ciudad = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        f"//div[contains(@class, 'ui fluid search selection dropdown')][.//input[@id='{PREVISORA_ID_CIUDAD_HIDDEN_FORM}']]",
                    )
                )
            )
            dropdown_container_ciudad.click()
            opcion_ciudad = wait.until(
                EC.element_to_be_clickable((By.XPATH, PREVISORA_XPATH_CIUDAD_OPCION))
            )
            opcion_ciudad.click()
        logs.append("    - Ciudad OK.")

        # Ingresar Factura
        logs.append(f"    Ingresando Factura '{codigo_factura}'...")
        input_factura = wait.until(
            EC.element_to_be_clickable((By.ID, PREVISORA_ID_FACTURA_FORM))
        )
        input_factura.clear()
        input_factura.send_keys(codigo_factura)
        logs.append("    - Factura OK.")

        # Ingresar Correo
        logs.append(f"    Ingresando Correo '{PREVISORA_CORREO_FORM}'...")
        input_correo = wait.until(
            EC.element_to_be_clickable((By.ID, PREVISORA_ID_CORREO_FORM))
        )
        input_correo.send_keys(Keys.CONTROL + "a")
        input_correo.send_keys(Keys.DELETE)
        input_correo.send_keys(PREVISORA_CORREO_FORM)
        logs.append("    - Correo OK.")

        # Ingresar Usuario
        logs.append(f"    Ingresando Usuario '{PREVISORA_USUARIO_REGISTRA_FORM}'...")
        input_usuario = wait.until(
            EC.element_to_be_clickable((By.ID, PREVISORA_ID_USUARIO_REGISTRA_FORM))
        )
        input_usuario.clear()
        input_usuario.send_keys(PREVISORA_USUARIO_REGISTRA_FORM)
        logs.append("    - Usuario OK.")

        # Seleccionar Ramo y esperar siguiente elemento o pop-up
        logs.append(f"    Seleccionando Ramo '{PREVISORA_RAMO_FORM}'...")
        try:
            select_ramo = Select(
                wait.until(EC.element_to_be_clickable((By.ID, PREVISORA_ID_RAMO_FORM)))
            )
            select_ramo.select_by_visible_text(PREVISORA_RAMO_FORM)
            logs.append("    - Ramo OK.")
        except (TimeoutException, NoSuchElementException) as e_ramo:
            logs.append(
                f"ERROR o Timeout esperando campo Ramo ({type(e_ramo).__name__}). Posible sesión expirada."
            )
            # Podríamos verificar driver.current_url aquí si queremos más certeza
            return ESTADO_FALLO, "\n".join(logs)

        logs.append("      Esperando posible pop-up factura duplicada...")

        try:
            WebDriverWait(driver, 10).until(  # Espera hasta 10s
                EC.any_of(  # Espera que CUALQUIERA de estas condiciones se cumpla
                    EC.visibility_of_element_located(
                        (
                            By.XPATH,
                            "//div[contains(@class, 'jconfirm') and contains(@class, 'jconfirm-open')]",
                        )
                    ),  # Pop-up visible
                    EC.element_to_be_clickable(
                        (By.ID, PREVISORA_ID_AMPAROS_FORM)
                    ),  # Campo Amparos clickable
                )
            )
            logs.append("      Elemento siguiente (Pop-up) detectado.")
        except TimeoutException:
            logs.append("      ADVERTENCIA: No se detectó pop-up de factura.")

        # Manejar pop-up de factura duplicada (si aparece)
        popup_aparecio, popup_log_str = _handle_popup_previsora(
            driver,
            wait,
            8,
            "//div[contains(@class, 'jconfirm') and contains(@class, 'jconfirm-open')]",
            PREVISORA_XPATH_POPUP_FACTURA_CONTINUAR,
            "Pop-up Factura Duplicada/Existente",
        )
        if popup_log_str:  # Añadir solo si no es None o vacío
            logs.append(popup_log_str)

        # --- **NUEVA VERIFICACIÓN CAMPO FACTURA** ---
        logs.append("    Verificando campo 'N° factura' post manejo de pop-up...")
        try:
            time.sleep(0.2)  # Pausa mínima por si acaso
            input_factura_actual = driver.find_element(By.ID, PREVISORA_ID_FACTURA_FORM)
            valor_actual_factura = input_factura_actual.get_attribute("value")
            logs.append(
                f"      Valor actual en campo factura: '{valor_actual_factura}'"
            )

            if (
                not valor_actual_factura
                or valor_actual_factura.strip() != codigo_factura.strip()
            ):
                logs.append(
                    "    -> ¡CAMPO FACTURA VACÍO O INCORRECTO! Omitiendo por posible duplicado/reseteo."
                )
                estado_final = ESTADO_OMITIDO_DUPLICADA
                return estado_final, "\n".join(logs)
            else:
                logs.append("      Campo factura conserva el valor correcto.")
        except (NoSuchElementException, TimeoutException) as e_verif:
            logs.append(
                f"ERROR: No se pudo encontrar/verificar el campo factura ({type(e_verif).__name__})."
            )
            return ESTADO_FALLO, "\n".join(logs)
        # --- **FIN NUEVA VERIFICACIÓN** ---

        # --- Continuar llenando SOLO si el campo factura está OK ---
        try:
            logs.append(
                f"    Seleccionando Amparos (Valor={PREVISORA_VALUE_AMPARO_FORM})..."
            )
            select_amparos = Select(
                wait.until(
                    EC.element_to_be_clickable((By.ID, PREVISORA_ID_AMPAROS_FORM))
                )
            )
            select_amparos.select_by_value(PREVISORA_VALUE_AMPARO_FORM)
            logs.append("    - Amparos OK.")

            logs.append(
                f"    Seleccionando Tipo Cuenta (Valor={PREVISORA_VALUE_TIPO_CUENTA_FORM})..."
            )
            select_tipo_cuenta = Select(
                wait.until(
                    EC.element_to_be_clickable((By.ID, PREVISORA_ID_TIPO_CUENTA_FORM))
                )
            )
            select_tipo_cuenta.select_by_value(PREVISORA_VALUE_TIPO_CUENTA_FORM)
            logs.append("    - Tipo Cuenta OK.")

        except (TimeoutException, NoSuchElementException) as e_final_form:
            logs.append(
                f"ERROR o Timeout llenando Amparos/Tipo Cuenta ({type(e_final_form).__name__}). Posible sesión expirada."
            )
            return ESTADO_FALLO, "\n".join(logs)

        logs.append("  Formulario principal llenado correctamente.")
        estado_final = ESTADO_EXITO
        return estado_final, "\n".join(logs)

    # --- Bloques except generales ---
    except (
        TimeoutException,
        NoSuchElementException,
        ElementClickInterceptedException,
    ) as e_selenium:
        logs.append(
            f"ERROR Selenium llenando formulario ({type(e_selenium).__name__}): {e_selenium}. Asumiendo sesión expirada."
        )
        traceback.print_exc()
        # ... (opcional: guardar captura de error) ...
        return ESTADO_FALLO, "\n".join(logs)
    except Exception as e:
        error_msg = f"  ERROR inesperado al llenar formulario: {e}"
        logs.append(error_msg)
        traceback.print_exc()
        # ... (opcional: guardar captura de error) ...
        return ESTADO_FALLO, "\n".join(logs)

    except (
        TimeoutException,
        NoSuchElementException,
        ElementClickInterceptedException,
    ) as e_selenium:
        # Asumir que estos errores en otras partes del llenado pueden ser sesión expirada
        logs.append(
            f"ERROR Selenium llenando formulario ({type(e_selenium).__name__}): {e_selenium}. Asumiendo sesión expirada."
        )
        traceback.print_exc()
        return ESTADO_FALLO, "\n".join(logs)
    except Exception as e:
        error_msg = f"  ERROR inesperado al llenar formulario: {e}"
        logs.append(error_msg)
        traceback.print_exc()
        return ESTADO_FALLO, "\n".join(logs)


def subir_y_enviar_previsora(driver, wait, pdf_path) -> tuple[bool, str]:
    """Carga PDF, envía formulario y maneja pop-ups. Retorna (exito, logs)."""
    logs = ["  Iniciando carga de archivo y envío..."]
    pdf_path_obj = Path(pdf_path)

    try:
        logs.append(
            f"    Buscando input archivo (ID={PREVISORA_ID_INPUT_FILE_FORM})..."
        )
        input_file = wait.until(
            EC.presence_of_element_located((By.ID, PREVISORA_ID_INPUT_FILE_FORM))
        )

        if not pdf_path_obj.is_file():
            return ESTADO_FALLO, "\n".join(
                logs + [f"ERROR PDF no encontrado: {pdf_path}"]
            )

        logs.append(f"    Cargando: {pdf_path_obj.name}")
        input_file.send_keys(str(pdf_path_obj))
        logs.append("    - Archivo enviado al input.")

        try:
            logs.append(
                f"    Buscando botón 'Enviar' (ID={PREVISORA_ID_BOTON_ENVIAR_FORM})..."
            )
            boton_enviar = wait.until(
                EC.element_to_be_clickable((By.ID, PREVISORA_ID_BOTON_ENVIAR_FORM))
            )
            logs.append("    Clic 'Enviar'...")
            driver.execute_script("arguments[0].scrollIntoView(true);", boton_enviar)
            time.sleep(0.1)  # Pausa mínima
            driver.execute_script("arguments[0].click();", boton_enviar)
            logs.append("    - Clic Enviar OK.")
        except (TimeoutException, NoSuchElementException) as e_enviar:
            logs.append(
                f"ERROR o Timeout esperando/clicando botón Enviar ({type(e_enviar).__name__}). Posible sesión expirada."
            )
            return ESTADO_FALLO, "\n".join(logs)

        # Manejar pop-up 'Sí, continuar'
        popup1_handled, popup1_log = _handle_popup_previsora(
            driver,
            wait,
            10,
            "//div[contains(@class, 'jconfirm') and contains(@class, 'jconfirm-open')]",
            PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR,
            "Pop-up 'Sí, continuar'",
        )
        logs.append(popup1_log)

        # Manejar pop-up 'Continuar y guardar'
        popup2_handled, popup2_log = _handle_popup_previsora(
            driver,
            wait,
            10,
            "//div[contains(@class, 'jconfirm') and contains(@class, 'jconfirm-open')]",
            PREVISORA_XPATH_POPUP_CONTINUAR_GUARDAR,
            "Pop-up 'Continuar y guardar'",
        )
        logs.append(popup2_log)

        logs.append("  Carga, envío y pop-ups intermedios completados.")
        return ESTADO_EXITO, "\n".join(logs)

    except (
        TimeoutException,
        NoSuchElementException,
        ElementClickInterceptedException,
    ) as e_selenium:
        error_msg = f"  ERROR Selenium subiendo/enviando ({type(e_selenium).__name__}): {e_selenium}. Asumiendo sesión expirada."
        logs.append(error_msg)
        traceback.print_exc()
        # Guardar captura de pantalla
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        error_screenshot_path = f"error_upload_submit_previsora_{timestamp}.png"
        try:
            driver.save_screenshot(error_screenshot_path)
            logs.append(f"Captura guardada: {error_screenshot_path}")
        except Exception as e_sc:
            logs.append(f"No se pudo guardar captura: {e_sc}")
        return ESTADO_FALLO, "\n".join(logs)
    except Exception as e:
        error_msg = f"  ERROR inesperado carga/envío/pop-ups Previsora: {e}"
        logs.append(error_msg)
        traceback.print_exc()
        return ESTADO_FALLO, "\n".join(logs)


def guardar_confirmacion_previsora(
    driver, wait, output_folder_path
) -> tuple[str | None, str | None, str]:
    """
    Espera pop-up final, EXTRAE RADICADO, guarda PDF, clica nueva reclamación.
    Retorna (ruta_pdf_guardado, codigo_radicado_extraido, mensaje_log).
    """
    logs = ["  Esperando POP-UP final 'Registro Generado'..."]
    output_folder = Path(output_folder_path)
    pdf_save_path = output_folder / "RAD.pdf"
    timestamp_file = time.strftime("%Y%m%d_%H%M%S")
    temp_png_path = output_folder / f"temp_confirmacion_{timestamp_file}.png"
    codigo_radicado_extraido = None

    try:
        wait_very_long = WebDriverWait(driver, 90)
        logs.append(f"    (Esperando hasta {wait_very_long._timeout}s...)")
        final_popup_element = wait_very_long.until(
            EC.visibility_of_element_located(
                (By.XPATH, PREVISORA_XPATH_FINAL_CONFIRMATION_POPUP_CONTAINER)
            )
        )
        logs.append("    Pop-up 'Registro Generado' detectado.")

        # Extracción de Radicado
        try:
            logs.append("    Intentando extraer código de radicado del pop-up...")
            texto_popup_completo = final_popup_element.text
            logs.append(
                f"      Texto completo del pop-up (aprox): '{texto_popup_completo[:200]}...'"
            )
            match_radicado = re.search(
                r"Tu codigo es:(?:\s| )*'(\d+)'", texto_popup_completo, re.IGNORECASE
            )  # Añadido IGNORECASE
            if match_radicado:
                codigo_radicado_extraido = match_radicado.group(1)
                logs.append(
                    f"      -> Código de Radicado extraído: {codigo_radicado_extraido}"
                )
            else:
                logs.append(
                    "      ADVERTENCIA: Patrón de radicado no encontrado en texto del pop-up."
                )
                codigo_radicado_extraido = "Extracción fallida"
        except Exception as e_extract:
            logs.append(f"      ADVERTENCIA: Error extrayendo radicado: {e_extract}")
            traceback.print_exc()
            codigo_radicado_extraido = "Error extracción"

        # ... (Esperar botón Nueva Reclamación) ...
        try:
            wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, PREVISORA_XPATH_BOTON_NUEVA_RECLAMACION)
                )
            )
            logs.append("Botón Nueva Rec. listo.")
        except TimeoutException:
            logs.append("ADVERTENCIA: No se esperó botón Nueva Rec.")
            time.sleep(1)

        # ... (Guardar captura PNG) ...
        if not driver.save_screenshot(str(temp_png_path)):
            raise Exception("Fallo guardar PNG")
        if not temp_png_path.is_file():
            raise Exception("PNG no creado")
            logs.append("Captura guardada.")

        # ... (Guardar PNG como PDF) ...
        logs.append(f"Guardando PDF: {pdf_save_path.name}")
        try:
            with Image.open(temp_png_path) as img:
                img_to_save = img.convert("RGB") if img.mode in ["RGBA", "P"] else img
                if pdf_save_path.exists():
                    pdf_save_path.unlink(missing_ok=True)  # Python 3.8+
                img_to_save.save(
                    str(pdf_save_path), "PDF", resolution=100.0, save_all=False
                )
        except Exception as e_save:
            raise Exception(f"Error guardando PDF: {e_save}")
        if not pdf_save_path.is_file():
            raise Exception("PDF no creado.")
            logs.append(f"PDF guardado: {pdf_save_path.name}")

        # --- Clic en 'Generar nueva reclamación' ---
        try:
            boton_nueva = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH, PREVISORA_XPATH_BOTON_NUEVA_RECLAMACION)
                )
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", boton_nueva)
            time.sleep(0.1)
            driver.execute_script("arguments[0].click();", boton_nueva)
            logs.append("Clic OK 'Generar nueva'.")
            try:  # Espera mejorada
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.ID, PREVISORA_ID_ELEMENTO_CLAVE_FORMULARIO)
                    )
                )
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.ID, PREVISORA_ID_FACTURA_FORM))
                )
                logs.append("Formulario listo para nueva reclamación.")
            except TimeoutException:
                logs.append(
                    "ADVERTENCIA: Formulario no pareció recargarse/interactuable post-'Generar nueva'."
                )
                # Este es un punto donde la sesión podría haber terminado si la recarga falla y nos lleva a login
                # pero no devolvemos ESTADO_SESION_EXPIRADA, solo es una advertencia.
        except (TimeoutException, ElementClickInterceptedException) as e_nueva:
            logs.append(
                f"ADVERTENCIA: No se pudo hacer clic en 'Generar nueva reclamación' o verificar recarga: {type(e_nueva).__name__}"
            )
            # No se considera un fallo total de la radicación actual, ya que el PDF se guardó.

        return (
            str(pdf_save_path),
            codigo_radicado_extraido,
            "\n".join(logs),
        )  # Devuelve 3 valores

    except TimeoutException as e_timeout_main:  # Específico para el wait_very_long
        error_msg = f"  ERROR CRÍTICO: Timeout ({wait_very_long._timeout}s) esperando POP-UP 'Registro Generado'."
        logs.append(error_msg)
        traceback.print_exc()
        # ... (guardar captura de error si es necesario) ...
        return None, None, "\n".join(logs)  # Retorna None para PDF y radicado
    except Exception as e:
        error_msg = f"  ERROR inesperado en confirmación/guardado PDF: {e}"
        logs.append(error_msg)
        traceback.print_exc()
        # ... (guardar captura de error si es necesario) ...
        return None, None, "\n".join(logs)  # Retorna None para PDF y radicado
    finally:
        if temp_png_path and temp_png_path.is_file():
            try:
                temp_png_path.unlink(missing_ok=True)  # Python 3.8+
            except OSError:
                pass


def procesar_carpeta_previsora(
    driver, wait, subfolder_path, subfolder_name
) -> tuple[str, str | None, str]:
    """
    Orquesta procesamiento. Retorna (estado, codigo_radicado, logs).
    """
    logs = [f"--- Iniciando Previsora: Carpeta '{subfolder_name}' ---"]
    subfolder_path_obj = Path(subfolder_path)
    codigo_radicado_final = None
    estado_final = ESTADO_FALLO

    try:
        # Asegúrate que la ruta sea correcta
        from Core.utilidades import encontrar_y_validar_pdfs
    except ImportError:
        logs.append("ERROR CRITICO: Import nucleo.utilidades")
        return ESTADO_FALLO, None, "\n".join(logs)

    # Verificar RAD.pdf
    if (subfolder_path_obj / "RAD.pdf").is_file():
        logs.append("  OMITIENDO: Ya existe RAD.pdf.")
        return ESTADO_OMITIDO_RADICADO, None, "\n".join(logs)

    try:
        # 1. Validar PDFs
        codigo_factura, pdf_path, pdf_val_log = encontrar_y_validar_pdfs(
            subfolder_path_obj, subfolder_name
        )
        logs.append(pdf_val_log)
        if not (codigo_factura and pdf_path and pdf_path.is_file()):
            return estado_final, None, "\n".join(logs)

        # 2. Llenar formulario (SIN verificación de página aquí)
        # llenar_formulario_previsora retorna (estado_str, logs_str)
        estado_llenado, fill_log = llenar_formulario_previsora(
            driver, wait, codigo_factura
        )
        logs.append(fill_log)
        if estado_llenado != ESTADO_EXITO:  # Si es FALLO o OMITIDO_DUPLICADA
            return estado_llenado, None, "\n".join(logs)

        # 3. Subir y enviar
        # subir_y_enviar_previsora retorna (estado_str, logs_str)
        estado_upload, upload_log = subir_y_enviar_previsora(driver, wait, pdf_path)
        logs.append(upload_log)
        if estado_upload != ESTADO_EXITO:  # Si es FALLO
            return estado_upload, None, "\n".join(logs)

        # 4. Guardar confirmación
        # *** ESTA ES LA LÍNEA DEL ERROR ***
        # Ahora esperamos 3 valores porque guardar_confirmacion_previsora los devuelve
        pdf_guardado_path, radicado_extraido, confirm_log_str = (
            guardar_confirmacion_previsora(driver, wait, subfolder_path_obj)
        )
        logs.append(confirm_log_str)  # Añadir los logs de la etapa de confirmación

        if pdf_guardado_path:  # Si se guardó el PDF, consideramos la radicación exitosa
            estado_final = ESTADO_EXITO
            codigo_radicado_final = radicado_extraido  # Puede ser None o el código
            rad_display = Path(pdf_guardado_path).name
            rad_code_display = (
                codigo_radicado_final
                if codigo_radicado_final
                else "No extraído/Falló extracción"
            )
            logs.append(
                f"--- {estado_final} Previsora: Carpeta '{subfolder_name}'. RAD: {rad_display} / Código Rad.: {rad_code_display} ---"
            )
        else:
            estado_final = ESTADO_FALLO  # Si no se guardó PDF, es fallo
            logs.append(
                f"--- {estado_final} Previsora: Carpeta '{subfolder_name}' falló en la confirmación/guardado. ---"
            )

        return estado_final, codigo_radicado_final, "\n".join(logs)

    except Exception as e_process:
        error_msg = f"[{subfolder_name}] !!! ERROR GENERAL ({estado_final}) !!!: {type(e_process).__name__} - {e_process}"
        logs.append(error_msg)
        logs.append(traceback.format_exc())
        # ... (opcional: guardar captura error) ...
        if "driver" in locals() and driver:
            try:
                ts_err = time.strftime("%Y%m%d_%H%M%S")
                err_sc = (
                    subfolder_path_obj
                    / f"error_proc_carpeta_{subfolder_name}_{ts_err}.png"
                )
                driver.save_screenshot(str(err_sc))
                logs.append(f"Captura guardada: {err_sc.name}")
            except:
                pass
        return ESTADO_FALLO, None, "\n".join(logs)
