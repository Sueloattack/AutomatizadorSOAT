import requests
from urllib.parse import quote_plus

# Define la URL base de la API, igual que en PHP.
# ¡ATENCIÓN! Esta URL de ngrok es temporal. Si reinicias ngrok, tendrás que actualizarla.
API_BASE_URL = 'https://asotrauma.ngrok.app/api-busqueda-gema/public/api'

def query_api_gema(sql_query: str) -> list:
    """
    Ejecuta una consulta SQL contra la API de GEMA.

    Esta función replica la lógica del cliente PHP:
    1. Codifica la consulta SQL para que sea segura en una URL.
    2. Realiza la petición HTTP GET usando la librería 'requests'.
    3. Valida la respuesta para detectar cualquier posible error.
    4. Devuelve únicamente el array de datos si la petición fue exitosa.

    :param sql_query: La consulta SQL a ejecutar (sin la palabra "SELECT").
    :return: Una lista de diccionarios con los datos devueltos por la API.
    :raises Exception: Si ocurre cualquier error durante la comunicación o si la API devuelve un error.
    """
    print(f"[API GEMA] Ejecutando: {sql_query[:200]}...")

    # 1. PREPARACIÓN DE LA URL (Equivalente a urlencode() y concatenación)
    # quote_plus codifica los espacios como '+' que es común en queries de URL.
    encoded_query = quote_plus(sql_query)
    url = f"{API_BASE_URL}/select/?query={encoded_query}"
    print(f"[API GEMA] URL final: {url}")


    # 2. COMUNICACIÓN Y MANEJO DE ERRORES
    try:
        # Ejecuta la petición GET. Se añade un timeout como buena práctica.
        response = requests.get(url, timeout=15) # 15 segundos de espera

        # 3.1. Error de Servidor (Código HTTP) (Equivalente a curl_getinfo)
        # response.raise_for_status() lanzaría un error para códigos 4xx o 5xx.
        # Haremos la comprobación manual para que el mensaje sea idéntico al de PHP.
        if response.status_code != 200:
            raise Exception(f"Error API GEMA. Código: {response.status_code}. Respuesta: {response.text}")

        # 3.2. Error de Formato JSON (Equivalente a json_decode y json_last_error)
        # .json() intentará decodificar la respuesta y lanzará un error si no es un JSON válido.
        response_data = response.json()

    # 3.3. Error de Conexión o de Red (Equivalente a curl_errno)
    # requests.exceptions.RequestException es la clase base para errores de conexión, timeout, etc.
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error de Conexión/Red: {e}")
    except ValueError: # requests.json() puede lanzar ValueError o JSONDecodeError
        raise Exception("Respuesta API no es un JSON válido.")


    # 3.4. Error Lógico de la API (Comprobando la estructura del JSON)
    # Usamos .get() para evitar errores si las claves no existen.
    if response_data.get('status') != 'success' or 'data' not in response_data:
        # Intenta obtener el mensaje de error de la API, o usa uno por defecto.
        error_message = response_data.get('message', 'Formato de respuesta inesperado.')
        raise Exception(f"API devolvió un error: {error_message}")


    # 4. DEVOLUCIÓN DEL RESULTADO
    # Si todo fue bien, devuelve solo el contenido de 'data'.
    return response_data['data']


# --- ZONA DE PRUEBAS ---
if __name__ == "__main__":
    # ¡MUY IMPORTANTE! La consulta NO debe incluir la palabra "SELECT".
    # Cambia esta consulta por una que funcione con tu base de datos.
    mi_consulta = "codigo, vr_glosa, motivo_res FROM [gema10.d/salud/datos/glo_det] WHERE gl_docn =   174118 and estatus1='C1'" # Ejemplo: obtén los primeros 5 usuarios

    try:
        # Llamamos a la función con nuestra consulta
        resultados = query_api_gema(mi_consulta)

        # Si todo va bien, imprimimos los resultados
        print("\n--- ¡Conexión exitosa! ---")
        print("Datos recibidos:")
        if resultados:
            for fila in resultados:
                print(fila)
        else:
            print("La consulta no devolvió resultados.")

    except Exception as e:
        # Si algo falla en el camino, capturamos la excepción y la mostramos.
        print(f"\n--- Ocurrió un error ---")
        print(e)