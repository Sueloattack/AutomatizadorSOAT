import fitz
import re
import os

def extraer_texto_primera_pagina(pdf_path):
    """Extrae el texto de la primera página del PDF."""
    try:
        doc = fitz.open(pdf_path)
        if len(doc) > 0:
            return doc[0].get_text()
        return ""
    except Exception as e:
        print(f"Error leyendo PDF {pdf_path}: {e}")
        return ""

def extraer_info_factura(texto):
    """
    Extrae la información clave del texto de la factura usando Regex.
    Retorna un diccionario con: entidad, poliza, anio, contrato, serie, numero.
    """
    info = {
        "entidad": None,
        "poliza": None,
        "anio": None,
        "contrato": None,
        "serie": None,
        "numero": None,
        "codigo_completo": None
    }

    # 1. ENTIDAD (Busca al inicio o patrones conocidos)
    patrones_entidad = [
        r"(MUNDIAL SEGUROS)",
        r"(AXA COLPATRIA)",
        r"(LA PREVISORA S\.A\.)",
        r"(SEGUROS DE VIDA DEL ESTADO)"
    ]
    for pat in patrones_entidad:
        match = re.search(pat, texto, re.IGNORECASE)
        if match:
            info["entidad"] = match.group(1).upper().replace(".", "")
            break

    # 2. POLIZA / CONTRATO / AÑO
    match_contrato = re.search(r"(SOAT|ARL|ESCOLAR|SALUD|MEDICINA PREPAGADA).*?AÑO\s*(\d{4})\s*-\s*(\d+)", texto, re.IGNORECASE)
    if match_contrato:
        info["poliza"] = match_contrato.group(1).upper()
        info["anio"] = match_contrato.group(2)
        info["contrato"] = match_contrato.group(3)
    else:
        match_poliza = re.search(r"(SOAT|ARL|ESCOLAR)", texto, re.IGNORECASE)
        if match_poliza:
            info["poliza"] = match_poliza.group(1).upper()

    # 3. SERIE Y NÚMERO DE FACTURA (Lógica Mejorada por Usuario)
    # Busca patrones como: N° FACTURA, FACTURA No., FACTURA ELECTRONICA No.
    numero_match = re.search(
        r'(?:N[°º]?\s*FACTURA|FACTURA.*?No\.?|FACTURA\s+ELECTRONICA.*?No\.?)\s*[:\-]?\s*([A-Z]{2,10})?\s*(\d+)',
        texto,
        re.IGNORECASE
    )
    
    if numero_match:
        # Grupo 1: Posible Serie (ej: "FE" en "FACTURA No. FE 123")
        if numero_match.group(1) and not info["serie"]:
            info["serie"] = numero_match.group(1).strip().upper()
        
        # Grupo 2: El Número (ej: "123")
        info["numero"] = numero_match.group(2).strip()
    
    # Plan B: Si aún no tenemos número, buscar cualquier secuencia larga de dígitos cerca de "FACTURA"
    if not info["numero"]:
        posible_numero = re.search(r'FACTURA[^\d]*(\d{4,})', texto, re.IGNORECASE)
        if posible_numero:
            info["numero"] = posible_numero.group(1).strip()

    # Intentar deducir serie si no se encontró explícitamente pero está en el nombre del archivo o contexto común
    if not info["serie"]:
         match_serie_simple = re.search(r"\b(COEX|FECR|FERD|FERR|FCR)\b", texto, re.IGNORECASE)
         if match_serie_simple:
             info["serie"] = match_serie_simple.group(1).upper()

    if info["serie"] and info["numero"]:
        info["codigo_completo"] = f"{info['serie']}{info['numero']}"
    elif info["numero"]:
         info["codigo_completo"] = info["numero"]

    return info
