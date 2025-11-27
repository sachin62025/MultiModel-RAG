# Multi-Modal Document Intelligence (RAG-based QA)

**Project:** Multi-Modal RAG QA — ingestion, retrieval, and grounded generation for documents (PDFs)
**Status:** Core system complete — FAISS semantic retrieval + table-aware chunking, OCR, numeric extraction, grounded generation.

---

## Overview

This project implements an end-to-end Retrieval-Augmented Generation (RAG) system that handles **multi-modal documents** (text, tables, images/OCR). It supports:

- Page rasterization + OCR for scanned PDFs
- Table row-level chunking for precise numeric extraction
- Vector embeddings (FAISS) for semantic retrieval
- Keyword-based reranking for exact matches
- Numeric extractors for high-precision answers (revenue, EPS, etc.)
- FastAPI demo app + simple HTML/JS UI
- Works without GPU

---

## Features

- Multi-modal ingestion: text, tables, embedded images, rasterized page images + OCR.
- Smart chunking: semantic + structural segmentation (table-row chunks).
- Vector index: FAISS-based embedding store with metadata.
- QA layers:
  - Numeric extractors (regex & table-aware)
  - Comparison extractors (current vs prior)
  - Certification & repurchase extractors
  - Generator fallback (FLAN-T5 or OpenAI)
- FastAPI UI: upload PDF, build index, query with citations and debug snippets.

---

## Repo layout

```
├─ web/
│ ├─ app.py
│ └─ templates/index.html
├─ ingest/
│ ├─ pdf_ingest.py
│ └─ ocr.py
├─ embeddings/
│ └─ embedder.py
├─ index/
│ ├─ faiss_index.py
│ └─ meta.pkl
├─ qa/
│ ├─ generator.py # answer_query pipeline (retrieval -> extract -> generate)
│ ├─ rerank.py
│ └─ extractors.py
├─ cli.py
├─ data/
└─ README.md
```


## Requirements

```
pip install -r requirements.txt
```

## Run locally

#### Ingest a PDF

```
python cli.py ingest path/to/NVIDIA-10Q-20242905.pdf --max-pages 50
```

#### Build the FAISS index

```
python cli.py index
```

### Direct with UI

```
uvicorn web.app:app --reload --host 0.0.0.0 --port 8000
```

##### Open UI

```
http://localhost:8000
```

## API Endpoints

- **POST `/upload`** — upload PDF (multipart/form-data `file`)
- **POST `/build_index`** — build FAISS index from ingested chunks
- **POST `/query`** — ask a question (form field `q`)
  - Response includes:
    - **`answer`** (string)
    - **`method`** (extraction | generation | extraction_comparison | ...)
    - **`citations`** (concise list with doc_id, page)
    - **`retrieved`** (top chunk snippets for debugging)
    - **`prompt`** (present only for generation; dev use)
- **GET `/status`** — check index/chunks availability
