# config.py
import os

DATA_DIR = os.getenv("MMR_DATA_DIR", "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
CHUNKS_PATH = os.path.join(DATA_DIR, "chunks.pkl")
INDEX_DIR = os.path.join(DATA_DIR, "index")
FAISS_INDEX_PATH = os.path.join(INDEX_DIR, "faiss.index")
META_PATH = os.path.join(INDEX_DIR, "meta.pkl")
TEXT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CLIP_MODEL = "ViT-B/32"  
