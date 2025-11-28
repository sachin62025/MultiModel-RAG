import pdfplumber
import os, io
from PIL import Image
from config import RAW_DIR
from ingest.ocr import ocr_image

os.makedirs(RAW_DIR, exist_ok=True)

def ingest_pdf(path, save_images=True):
    """
    Returns list of dicts: [{"doc_id": filename, "page": i, "text": text, "tables": tables, "images": [paths]}]
    """
    docs = []
    filename = os.path.basename(path)
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            # if page has very little text, run OCR on a rasterized page
            if len(text.strip()) < 20:
                # dump a page image and OCR it
                im = page.to_image(resolution=150)
                img_path = os.path.join(RAW_DIR, f"{filename}_page_{i}.png")
                im.save(img_path, format="PNG")
                ocr_text = ocr_image(img_path)
                text = (text + "\n" + ocr_text).strip()
            tables = [t for t in page.extract_tables() if t]
            images = []
            if save_images and page.images:
                for j, img in enumerate(page.images):
                    try:
                        bbox = (img["x0"], img["top"], img["x1"], img["bottom"])
                        cropped = page.within_bbox(bbox).to_image(resolution=150)
                        img_path = os.path.join(RAW_DIR, f"{filename}_page_{i}_img_{j}.png")
                        cropped.save(img_path, format="PNG")
                        images.append(img_path)
                    except Exception:
                        continue
            docs.append({"doc_id": filename, "page": i, "text": text, "tables": tables, "images": images})
    return docs
