# chunking/chunker.py
import re

def chunk_text(page_text, page_num, doc_id, chunk_size_chars=2000):
    """
    Splits text into chunks (~chunk_size_chars) on sentence boundaries.
    Returns list of chunk dicts with metadata.
    """
    if not page_text:
        return []
    sentences = re.split(r'(?<=[.!?])\s+', page_text)
    chunks = []
    cur = ""
    for s in sentences:
        if len(cur) + len(s) > chunk_size_chars:
            chunks.append(cur.strip())
            cur = s
        else:
            cur += " " + s
    if cur.strip():
        chunks.append(cur.strip())
    out = []
    for i, c in enumerate(chunks):
        out.append({
            "doc_id": doc_id,
            "page": page_num,
            "chunk_id": f"p{page_num}_c{i+1}",
            "type": "text",
            "text": c
        })
    return out

def chunk_table(table, page_num, doc_id):
    """
    Convert a table (list-of-rows) to flattened text.
    """
    if not table:
        return []
    # header detection: first row
    header = table[0]
    rows = table[1:] if len(table) > 1 else []
    lines = []
    lines.append(" | ".join([str(h) for h in header]))
    for r in rows:
        lines.append(" | ".join([str(x) for x in r]))
    text = "\n".join(lines)
    return [{
        "doc_id": doc_id,
        "page": page_num,
        "chunk_id": f"p{page_num}_table",
        "type": "table",
        "text": text
    }]
