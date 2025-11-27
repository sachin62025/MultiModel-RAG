# ingest/ocr.py
import easyocr
# easyocr loads language models on initialization; keep single reader
_reader = None

def _get_reader():
    global _reader
    if _reader is None:
        # english only; gpu=False to run on CPU
        _reader = easyocr.Reader(['en'], gpu=False)
    return _reader

def ocr_image(path):
    reader = _get_reader()
    try:
        results = reader.readtext(path, detail=0)
        return "\n".join(results)
    except Exception as e:
        print(f"OCR failed on {path}: {e}")
        return ""
