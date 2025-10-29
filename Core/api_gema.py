# Core/api_ggema.py

import requests
from urllib.parse import quote_plus
from Configuracion.constantes import MUNDIAL_ESCOLAR_API_BASE_URL # Importamos desde constantes

# Nota: Deberás añadir la URL base de tu API a tu archivo de constantes.
# En Configuracion/constantes.py, añade:
# MUNDIAL_ESCOLAR_API_BASE_URL = 'https://tu_dominio.ngrok.app/api-busqueda-gema/public/api'


def query_api_gema(sql_query: str) -> list:
    """
    Ejecuta una consulta SQL contra la API de GEMA y devuelve los resultados.
    
    Esta es una función de producción robusta que:
    1. Codifica la consulta SQL para que sea segura en la URL.
    2. Realiza la petición GET con timeouts adecuados.
    3. Valida códigos de estado HTTP.
    4. Valida que la respuesta sea un JSON válido.
    5. Valida la estructura de la respuesta JSON de la API (status 'success' y clave 'data').
    6. Lanza excepciones claras y específicas para cada tipo de error.

    Args:
        sql_query: La consulta SQL a ejecutar (sin la palabra "SELECT").

    Returns:
        Una lista de diccionarios, donde cada diccionario es una fila del resultado.

    Raises:
        Exception: Si ocurre cualquier error de conexión, timeout, formato o lógico de la API.
    """
    try:
        # 1. Codificar la consulta y construir la URL completa
        encoded_query = quote_plus(sql_query)
        url = f"{MUNDIAL_ESCOLAR_API_BASE_URL}/select/?query={encoded_query}"

        # 2. Realizar la petición GET
        # Se establece un timeout (conexión, lectura) como buena práctica.
        response = requests.get(url, timeout=(5, 20)) # 5 seg para conectar, 20 seg para recibir respuesta

        # 3. Validar el código de estado HTTP (éxito si es 200)
        if response.status_code != 200:
            raise ConnectionError(f"Error en la respuesta del servidor API. Código: {response.status_code}. Respuesta: {response.text[:200]}...") # Limitamos la longitud de la respuesta en el log

        # 4. Validar y decodificar la respuesta JSON
        response_data = response.json()

    # Manejar errores de conexión, timeouts, DNS, etc.
    except requests.exceptions.Timeout:
        raise TimeoutError("Timeout en la API: La consulta tardó demasiado en responder.")
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Error de conexión con la API de Gema: {e}")
    # Manejar el caso en que la respuesta no es un JSON válido
    except ValueError:
        raise TypeError(f"La respuesta de la API no es un JSON válido. Respuesta recibida: {response.text[:200]}...")

    # 5. Validar la estructura de la respuesta de la API
    # Usamos .get() para evitar KeyErrors si la estructura del JSON es incorrecta.
    status = response_data.get('status')
    data = response_data.get('data')

    if status != 'success':
        error_message = response_data.get('message', 'La API devolvió un estado de error sin mensaje.')
        raise ValueError(f"La API de Gema devolvió un error lógico: {error_message}")
    
    if data is None: # Se comprueba que la clave 'data' exista
        raise TypeError("La respuesta de la API tiene un formato inesperado (falta la clave 'data').")

    # 6. Devolver los datos si todas las validaciones pasan
    return data