# Plan de Desarrollo: Módulo de Automatización "Mundial Escolar"

## 1. Objetivo

Este documento describe el plan estratégico y el flujo lógico para la creación de un nuevo módulo de automatización para la entidad "Mundial Escolar". El objetivo es desarrollar un bot robusto, eficiente y mantenible que pueda manejar las complejidades específicas de esta plataforma, incluyendo:

1.  **Múltiples Sedes de Login:** Autenticación dinámica dependiendo del tipo de servicio.
2.  **Conciliación Compleja de Ítems:** Discrepancias entre los ítems de glosa presentados por la plataforma y los registrados en el software interno.
3.  **Flujo de Trabajo Basado en Carpetas:** Operación desatendida a partir de una estructura de directorios.

## 2. Arquitectura General

La solución se compondrá de cuatro componentes principales, integrados en la estructura del proyecto existente:

*   **Configuración Centralizada:** Almacenamiento de datos variables (URLs, credenciales) para facilitar el mantenimiento.
*   **Módulo de Lógica de Negocio:** Orquestador principal que contiene el flujo de trabajo del bot.
*   **Algoritmo de Conciliación Inteligente:** El núcleo que resuelve las discrepancias de ítems.
*   **Sistema de Reportes y Manejo de Errores:** Mecanismos para informar sobre el éxito, los fracasos y los casos que requieren intervención humana.

## 3. Fases del Proceso Lógico (End-to-End)

### Fase 1: Preparación y Clasificación de Tareas

El proceso inicia con el descubrimiento y organización de las tareas.

1.  **Input Inicial:** El usuario proporciona una **carpeta raíz** al programa.
2.  **Descubrimiento:** El bot escanea todas las subcarpetas inmediatas dentro de la carpeta raíz. Cada subcarpeta representa una glosa individual a procesar.
3.  **Clasificación por Sede:**
    *   Para cada subcarpeta, el bot determina si pertenece a `SEDE_1` o `SEDE_2`.
    *   **Regla de Clasificación:** Se debe establecer un método. Ej: El bot busca un archivo `datos.txt` dentro de la carpeta que especifique el tipo de servicio (ej. `COEX` o `FECR`) y usa un mapa en `constantes.py` para asignarlo a una sede.
    *   **Output:** Se generan dos listas de rutas de carpetas: `carpetas_para_sede_1` y `carpetas_para_sede_2`.

### Fase 2: Procesamiento por Lotes (Sede por Sede)

El bot procesa las glosas en grupos, optimizando los inicios de sesión.

1.  **Bucle por Sede:** Se inicia un bucle que procesará primero un lote completo (ej. `SEDE_1`) y luego el siguiente.
2.  **Login Único:** Al inicio de cada lote, se realiza **un solo login** en el portal de la sede correspondiente.
3.  **Bucle por Carpeta (Glosas):** Dentro del lote, se itera sobre cada `carpeta_actual`.
    1.  **Extraer Datos:** Se obtiene el número de glosa/factura a procesar desde la `carpeta_actual`.
    2.  **Búsqueda en Plataforma:** El bot busca la glosa en el portal.
    3.  **Manejo de Error - Glosa No Encontrada:**
        *   Si la glosa no se encuentra, el bot:
            1.  Toma una **captura de pantalla** del error.
            2.  La guarda en la `carpeta_actual` como `_GLOSA_NO_ENCONTRADA.png`.
            3.  Registra el evento en el log.
            4.  **Continúa** con la siguiente carpeta sin detenerse.
    4.  **Proceso de Conciliación (Si se encuentra la glosa):**
        1.  **Extracción de Ítems del Portal:** Se obtienen todos los ítems que la plataforma muestra para radicar.
        2.  **Llamada Única a API Interna:** Se realiza **una sola consulta** a la API interna para traer **toda** la información de esa glosa: códigos, valores y el texto de respuesta (`motivo_res`).
        3.  **Normalización de Datos:** Se limpian y estandarizan los datos de ambas fuentes (ej. `normalizar_codigo('6.23') -> '623'`).
        4.  **Ejecución del Algoritmo de Conciliación:**
            *   **Paso A (Verificación de Totales):** Se comparan los valores totales. Si no coinciden, la glosa se marca para revisión manual.
            *   **Paso B (Coincidencia 1 a 1):** Se buscan y emparejan las coincidencias directas por código y valor.
            *   **Paso C (Coincidencia Agrupada - Muchos a Uno):** Para ítems del portal sin pareja, se buscan combinaciones de ítems internos que sumen su valor.
            *   **Paso D (Coincidencia Dividida - Uno a Muchos):** Proceso inverso al anterior para los ítems internos restantes.
        5.  **Radicación en Plataforma:**
            *   Por cada conciliación exitosa, el bot navega al ítem correspondiente.
            *   Pega el texto del campo `motivo_res` (obtenido de la API) en el campo de respuesta del portal.
            *   Radica el ítem.
        6.  **Reporte por Carpeta:** Se genera un archivo de resumen (`_reporte.txt`) en la `carpeta_actual` con el resultado del proceso para esa glosa.
4.  **Logout:** Al finalizar todas las carpetas de un lote, el bot cierra la sesión.

## 4. Componente Clave: Algoritmo de Conciliación

Este es el núcleo lógico para resolver las discrepancias.

*   **Técnica:** Se basa en una búsqueda recursiva con **backtracking**, una solución clásica para el "Problema de la suma de subconjuntos" (Subset Sum Problem).
*   **Optimización Principal:** La búsqueda de combinaciones se filtra **siempre por el código normalizado**. El bot no intentará combinar ítems con códigos de servicio diferentes, reduciendo drásticamente la complejidad.
*   **Manejo de Estado:** Se utiliza una bandera `usado` en las estructuras de datos para asegurar que cada ítem (tanto del portal como interno) se utilice en una sola conciliación.

## 5. Estructura de Archivos Sugerida

*   `Configuracion/constantes.py`: Almacenará las URLs, credenciales y el mapeo de servicios a sedes.
*   `Automatizaciones/glosas/mundial_escolar.py`: Contendrá la clase o funciones principales del bot, implementando el flujo de trabajo descrito.
*   `Core/generador_reportes.py`: Se utilizará para generar los informes finales consolidados.

## 6. Beneficios del Diseño

*   **Eficiencia:** Minimiza las llamadas a la API interna y los inicios de sesión en el portal.
*   **Robustez:** Maneja errores esperados (glosa no encontrada) de forma inteligente y aísla los problemas de conciliación para revisión humana sin detener el proceso general.
*   **Mantenibilidad:** La separación de la configuración, la lógica y la conciliación facilita futuras actualizaciones y correcciones.

