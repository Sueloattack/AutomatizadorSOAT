# AutomatizadorSOAT/nucleo/generador_reportes.py
"""
Funciones para generar el reporte PDF usando reportlab.
"""
from pathlib import Path
import traceback
import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import inch
from reportlab.lib import colors


def crear_reporte_pdf(
    ruta_archivo_pdf: Path, nombre_carpeta_padre: str, datos_tabla: list
):
    """
    Crea el archivo REPORTE.pdf con los datos proporcionados.

    Args:
        ruta_archivo_pdf: Objeto Path donde se guardará el PDF.
        nombre_carpeta_padre: Nombre de la carpeta contenedora para el título.
        datos_tabla: Lista de listas, donde cada lista interna es una fila de datos
                (incluyendo la fila de encabezados).
                Ej: [['Codigo Subcarpeta', 'Factura', 'Radicado', 'Fecha'], ['sub1', 'f1', 'r1', 'd1'], ...]
    """
    try:
        doc = SimpleDocTemplate(str(ruta_archivo_pdf))
        styles = getSampleStyleSheet()
        story = []

        # --- Estilos Personalizados ---
        style_titulo = styles["h1"]
        style_titulo.alignment = TA_CENTER
        style_titulo.fontSize = 18
        style_titulo.spaceAfter = 0.3 * inch

        style_normal_c = styles["Normal"]
        style_normal_c.alignment = TA_CENTER

        style_normal_l = styles["Normal"]
        style_normal_l.alignment = TA_LEFT

        # --- Título ---
        titulo = Paragraph(
            f"Reporte Automatización - {nombre_carpeta_padre}", style_titulo
        )
        story.append(titulo)
        # story.append(Spacer(1, 0.2 * inch))

        # --- Tabla ---
        if (
            not datos_tabla or len(datos_tabla) < 2
        ):  # Debe tener encabezados y al menos una fila de datos
            story.append(
                Paragraph(
                    "No se encontraron datos de carpetas procesadas con éxito.",
                    style_normal_c,
                )
            )
        else:
            # Ajustar anchos de columna (aproximado, basado en 6 pulgadas de ancho útil)
            # Col 1 (Subcarpeta), Col 2 (Factura), Col 3 (Radicado), Col 4 (Fecha)
            col_widths = [1.5 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch]

            tabla = Table(datos_tabla, colWidths=col_widths)

            # Estilo de la tabla
            style_tabla = TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),  # Encabezado gris
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        colors.whitesmoke,
                    ),  # Texto encabezado blanco
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),  # Centrar todo por defecto
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, 0),
                        "Helvetica-Bold",
                    ),  # Encabezado en negrita
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, 0),
                        12,
                    ),  # Espaciado debajo del encabezado
                    (
                        "BACKGROUND",
                        (0, 1),
                        (-1, -1),
                        colors.beige,
                    ),  # Fondo de datos beige (opcional)
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),  # Rejilla negra
                ]
            )
            tabla.setStyle(style_tabla)
            story.append(tabla)

        # --- Construir PDF ---
        doc.build(story)
        return True, f"Reporte generado con éxito en: {ruta_archivo_pdf.name}"

    except Exception as e:
        error_msg = f"Error al generar el PDF: {e}"
        traceback.print_exc()
        return False, error_msg
