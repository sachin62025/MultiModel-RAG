# web/app.py
import os, io, pickle
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from starlette.middleware.cors import CORSMiddleware
from ingest.pdf_ingest import ingest_pdf
from chunking.chunker import chunk_text, chunk_table
from embeddings.embedder import embed_texts
from index.faiss_index import build_faiss_index, load_index, search_index
# from qa.generator import retrieve, assemble_prompt, generate_answer
from config import RAW_DIR, CHUNKS_PATH, FAISS_INDEX_PATH, META_PATH, INDEX_DIR
from qa.generator import answer_query
import numpy as np

app = FastAPI(title="Multi-Modal RAG QA")

# allow local web UI use
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
os.makedirs(TEMPLATES_DIR, exist_ok=True)
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Simple index page (will render template below)
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Upload PDF
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    contents = await file.read()
    save_path = os.path.join(RAW_DIR, file.filename)
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(contents)
    # run ingest immediately
    docs = ingest_pdf(save_path)
    # docs = ingest_pdf(save_path, save_page_images=True, ocr_every_page=True, dpi=150, max_pages=50) # this is for all pages set as 50 
    # chunk and save chunks
    chunks = []
    for p in docs:
        chunks.extend(chunk_text(p['text'], p['page'], p['doc_id']))
        for t in p['tables']:
            chunks.extend(chunk_table(t, p['page'], p['doc_id']))
        for img in p['images']:
            chunks.append({"doc_id": p['doc_id'], "page": p['page'], "chunk_id": f"p{p['page']}_img", "type":"image", "text": f"[Image: {img}]", "image_path": img})
    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(chunks, f)
    return JSONResponse({"status":"ok", "message": f"Saved {len(chunks)} chunks", "file": file.filename})

# Build index
@app.post("/build_index")
async def build_index():
    if not os.path.exists(CHUNKS_PATH):
        return JSONResponse({"status":"error","message":"No chunks found. Upload a PDF first."})
    with open(CHUNKS_PATH, "rb") as f:
        chunks = pickle.load(f)
    texts = [c.get("text","") for c in chunks]
    vecs = embed_texts(texts)
    vecs = np.array(vecs).astype("float32")
    build_faiss_index(vecs, chunks)
    return JSONResponse({"status":"ok","message":"Index built"})


# @app.post("/build_index")
# async def build_index():
#     if not os.path.exists(CHUNKS_PATH):
#         return JSONResponse({"status":"error","message":"No chunks found. Upload a PDF first."})
#     with open(CHUNKS_PATH, "rb") as f:
#         chunks = pickle.load(f)
#     texts = [c.get("text","") for c in chunks]
#     vecs = embed_texts(texts)
#     vecs = np.array(vecs).astype("float32")
#     build_faiss_index(vecs, chunks)
#     # Build BM25 too
#     build_bm25_index(chunks)
#     return JSONResponse({"status":"ok","message":"Index (FAISS + BM25) built"})


# Query endpoint
# @app.post("/query")
# async def query(q: str = Form(...)):
#     try:
#         resp = answer_query(q, top_k=20, use_openai=False, openai_client=None)
#         # normalize response for UI
#         if resp.get("method") == "extraction":
#             answer = resp["answer"]
#             citation = resp["citation"]
#             citations = [citation]
#         else:
#             answer = resp["answer"]
#             citations = resp.get("citations", [])
#         return JSONResponse({"query": q, "answer": answer, "method": resp.get("method"), "citations": citations})
#     except Exception as e:
#         return JSONResponse({"status":"error","message": str(e)})
    
# web/app.py  -- replace the /query endpoint with this implementation

from fastapi import Form
from fastapi.responses import JSONResponse
SNIPPET_CHARS = 600

@app.post("/query")
async def query(q: str = Form(...)):
    """
    Query endpoint:
     - calls answer_query(...)
     - returns answer, method, citations, and a short list of retrieved chunk snippets
     - includes the prompt when generation is used (for debugging)
    """
    try:
        resp = answer_query(q, top_k=20, use_openai=False, openai_client=None)

        # canonicalize fields
        method = resp.get("method", "unknown")
        answer = resp.get("answer", "")
        prompt = resp.get("prompt", None)

        # Build compact citation objects for UI
        citations = resp.get("citations", [])
        # citations may be already in different shapes (extraction returned 'citation' single item)
        if not isinstance(citations, list):
            # try to wrap single citation
            citations = [citations] if citations else []

        # Build retrieved snippet list (for debugging): include doc_id, page, chunk_id, short text
        retrieved = []
        raw_retrieved = resp.get("retrieved", [])  # list of chunk dicts
        for c in raw_retrieved:
            if not c:
                continue
            txt = c.get("text", "")
            snippet = txt.strip()
            if len(snippet) > SNIPPET_CHARS:
                snippet = snippet[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "..."
            retrieved.append({
                "doc_id": c.get("doc_id"),
                "page": c.get("page"),
                "chunk_id": c.get("chunk_id"),
                "type": c.get("type"),
                "score": c.get("score"),   # optional, may be None
                "snippet": snippet
            })

        response_payload = {
            "query": q,
            "answer": answer,
            "method": method,
            "citations": citations,
            "retrieved": retrieved,
        }
        # include prompt only when present (mainly for generation debugging)
        if prompt:
            response_payload["prompt"] = prompt

        return JSONResponse(response_payload)

    except Exception as e:
        # keep error messages concise but informative for debugging
        return JSONResponse({"status": "error", "message": str(e)})



# simple health
@app.get("/status")
def status():
    idx_exists = os.path.exists(FAISS_INDEX_PATH)
    chunks_exists = os.path.exists(CHUNKS_PATH)
    return {"index": idx_exists, "chunks": chunks_exists}
