# embeddings/embedder.py
from sentence_transformers import SentenceTransformer
import numpy as np
import torch
from PIL import Image
import os
import clip

from config import TEXT_EMBED_MODEL, CLIP_MODEL

# text embedder (small)
_text_model = None
# clip model & preprocess
_clip_model = None
_clip_preprocess = None
_device = "cpu"

def get_text_model():
    global _text_model
    if _text_model is None:
        _text_model = SentenceTransformer(TEXT_EMBED_MODEL)
    return _text_model

def embed_texts(texts, batch_size=32):
    """
    texts: list[str]
    returns: numpy array shape (n, d) dtype=float32
    """
    model = get_text_model()
    embs = model.encode(texts, batch_size=batch_size, show_progress_bar=False, convert_to_numpy=True)
    return embs.astype("float32")

def get_clip():
    global _clip_model, _clip_preprocess
    if _clip_model is None:
        _clip_model, _clip_preprocess = clip.load(CLIP_MODEL, device=_device)
    return _clip_model, _clip_preprocess

def embed_image(path):
    """
    path: image file path
    returns: numpy array (1, d) float32
    """
    model, preprocess = get_clip()
    image = preprocess(Image.open(path)).unsqueeze(0).to(_device)
    with torch.no_grad():
        img_emb = model.encode_image(image).cpu().numpy()
    return img_emb.astype("float32")
