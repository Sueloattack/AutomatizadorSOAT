import fitz
import re
from pathlib import Path

def extract_text_sample(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        return str(e)

base_path = Path(r"c:\Users\GLOSAS\Documents\JJAC\AutomatizadorSOAT\Pruebas")
sample_pdf = base_path / "COEX29786.pdf"

if sample_pdf.exists():
    print(f"--- Extracting text from {sample_pdf.name} ---")
    content = extract_text_sample(sample_pdf)
    print(content[:2500]) # Print first 2000 chars
else:
    print("Sample file not found.")
