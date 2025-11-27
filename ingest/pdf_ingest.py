# ingest/pdf_ingest.py
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

# # ingest/pdf_ingest.py  (pdfplumber rasterize + OCR for each page)
# import pdfplumber
# import os, io
# from PIL import Image
# from ingest.ocr import ocr_image
# from config import RAW_DIR

# os.makedirs(RAW_DIR, exist_ok=True)

# def ingest_pdf(path, save_page_images=True, ocr_every_page=True, dpi=150, max_pages=None):
#     """
#     Ingest PDF and ensure each page is rasterized and OCR'd.
#     - save_page_images: save a rasterized page image for each page (recommended True)
#     - ocr_every_page: run OCR on every page image if text is short or missing
#     - dpi: rasterization resolution (150-300 good)
#     - max_pages: if set, process only first N pages (useful for testing)
#     Returns list of page dicts: {doc_id, page, text, tables, images}
#     """
#     docs = []
#     filename = os.path.basename(path)
#     with pdfplumber.open(path) as pdf:
#         num_pages = len(pdf.pages)
#         for i, page in enumerate(pdf.pages, start=1):
#             if max_pages and i > max_pages:
#                 break
#             # extract existing textual layer
#             text = page.extract_text() or ""
#             tables = [t for t in page.extract_tables() if t]
#             images = []

#             # rasterize page to an image file (guarantees page image)
#             if save_page_images:
#                 pil_img = page.to_image(resolution=dpi).original
#                 img_path = os.path.join(RAW_DIR, f"{filename}_page_{i}.png")
#                 pil_img.save(img_path, format="PNG")
#                 images.append(img_path)

#                 # If textual extraction is empty or we want OCR on every page, run OCR
#                 if ocr_every_page and (len(text.strip()) < 20):
#                     ocr_text = ocr_image(img_path)
#                     if ocr_text:
#                         # append OCR text to extracted text (avoid overwriting)
#                         text = (text + "\n" + ocr_text).strip()

#             # Also attempt to extract any embedded images (figures)
#             if page.images:
#                 # Save embedded images (may duplicate page image sometimes)
#                 for j, img in enumerate(page.images):
#                     try:
#                         bbox = (img["x0"], img["top"], img["x1"], img["bottom"])
#                         cropped = page.within_bbox(bbox).to_image(resolution=dpi)
#                         emb_path = os.path.join(RAW_DIR, f"{filename}_page_{i}_embimg_{j}.png")
#                         cropped.save(emb_path, format="PNG")
#                         images.append(emb_path)
#                     except Exception:
#                         continue

#             docs.append({"doc_id": filename, "page": i, "text": text, "tables": tables, "images": images})
#     return docs
