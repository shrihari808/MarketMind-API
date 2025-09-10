import fitz  # PyMuPDF
import camelot
import tempfile
import os

def deconstruct_pdf(pdf_path: str) -> dict:
    text = ""
    images = []
    tables = []

    # Text and Image Extraction with PyMuPDF
    doc = fitz.open(pdf_path)
    for page_num, page in enumerate(doc):
        text += page.get_text()
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(image_bytes)
                images.append({"page_number": page_num + 1, "image_path": tmp.name})

    # Table Extraction with Camelot
    camelot_tables = camelot.read_pdf(pdf_path, pages='all')
    for table in camelot_tables:
        tables.append({"page_number": table.page, "data_as_markdown": table.df.to_markdown()})

    return {
        "text": text,
        "images": images,
        "tables": tables
    }