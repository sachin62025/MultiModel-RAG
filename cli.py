# cli.py
import typer, os, pickle
from ingest.pdf_ingest import ingest_pdf
from chunking.chunker import chunk_text, chunk_table
from embeddings.embedder import embed_texts, embed_image
from index.faiss_index import build_faiss_index
from config import RAW_DIR, CHUNKS_PATH

app = typer.Typer()

@app.command()
def ingest(pdf_path: str):
    docs = ingest_pdf(pdf_path)
    chunks = []
    for p in docs:
        # text chunks
        text_chunks = chunk_text(p['text'], p['page'], p['doc_id'])
        chunks.extend(text_chunks)
        # tables
        for t in p['tables']:
            chunks.extend(chunk_table(t, p['page'], p['doc_id']))
        # images: store as chunk with image path as attribute (we don't embed images into same vector here)
        for img in p['images']:
            chunks.append({"doc_id": p['doc_id'], "page": p['page'], "chunk_id": f"p{p['page']}_img", "type": "image", "text": f"[Image: {img}]", "image_path": img})
    os.makedirs(os.path.dirname(CHUNKS_PATH), exist_ok=True)
    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(chunks, f)
    typer.echo(f"Ingested and saved {len(chunks)} chunks to {CHUNKS_PATH}")

@app.command()
def index():
    # load chunks
    with open(CHUNKS_PATH, "rb") as f:
        chunks = pickle.load(f)
    texts = [c.get("text","") for c in chunks]
    # embed text chunks only (images can be embedded separately if desired)
    vecs = embed_texts(texts)
    import numpy as np
    vecs = np.array(vecs).astype("float32")
    build_faiss_index(vecs, chunks)
    typer.echo("Built FAISS index.")

if __name__ == "__main__":
    app()
