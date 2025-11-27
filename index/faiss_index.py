# index/faiss_index.py
import faiss
import numpy as np
import os, pickle
from config import FAISS_INDEX_PATH, META_PATH, INDEX_DIR

def build_faiss_index(vectors, metadata, index_path=FAISS_INDEX_PATH, meta_path=META_PATH):
    """
    vectors: numpy array shape (n, d) float32
    metadata: list of dicts (same length n)
    """
    os.makedirs(INDEX_DIR, exist_ok=True)
    # normalize and use IndexFlatIP for cosine via normalized vectors
    vecs = vectors.copy()
    faiss.normalize_L2(vecs)
    dim = vecs.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vecs)
    faiss.write_index(index, index_path)
    with open(meta_path, "wb") as f:
        pickle.dump(metadata, f)
    return True

def load_index(index_path=FAISS_INDEX_PATH, meta_path=META_PATH):
    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        raise FileNotFoundError("Index or meta not found")
    index = faiss.read_index(index_path)
    import pickle
    with open(meta_path, "rb") as f:
        meta = pickle.load(f)
    return index, meta

def search_index(query_vec, top_k=5, index_path=FAISS_INDEX_PATH, meta_path=META_PATH):
    index, meta = load_index(index_path, meta_path)
    q = query_vec.copy()
    faiss.normalize_L2(q)
    D, I = index.search(q, top_k)
    results = []
    for idx in I[0]:
        results.append(meta[idx])
    return results, D[0]
