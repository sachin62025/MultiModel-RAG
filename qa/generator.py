# qa/generator.py
import os
import pickle
import re
from typing import List, Dict, Any
import numpy as np
from embeddings.embedder import embed_texts
from index.faiss_index import search_index
from config import CHUNKS_PATH
from embeddings.embedder import embed_texts
from index.faiss_index import search_index 
from qa.rerank import rerank_by_keyword
from qa.extractors import extract_numeric_candidates_from_chunks, extract_first_money_after_label
from transformers import pipeline
from qa.extractors import (
    extract_numeric_candidates_from_chunks,
    extract_comparison_from_chunks,
    extract_repurchases,
    extract_certification_text
)

_local_generator = None
def get_local_generator():
    global _local_generator
    if _local_generator is None:
        _local_generator = pipeline("text2text-generation", model="google/flan-t5-small", device=-1)
    return _local_generator

def assemble_numeric_prompt(query, top_chunks):
    ctx = ""
    for i, r in enumerate(top_chunks, 1):
        snippet = r.get("text","")
        ctx += f"\n[Source {i}] (doc:{r.get('doc_id')} page:{r.get('page')} type:{r.get('type')})\n{snippet}\n"
    prompt = (
        "You are an assistant. The user asked for a numeric fact. Use ONLY the context sources below to find the exact numeric value. "
        "Return ONE short sentence with the number and a citation in brackets like: \"$26,044 [Source 1]\". "
        "If the number is not present exactly in the context, say 'Not found in context'.\n\n"
        f"CONTEXT:{ctx}\n\nQUESTION: {query}\n\nAnswer:"
    )
    return prompt

def assemble_prompt(query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    ctx = ""
    for i, r in enumerate(retrieved_chunks, 1):
        ctx += f"\n[Source {i}] (doc:{r.get('doc_id')} page:{r.get('page')} type:{r.get('type')})\n{r.get('text','')}\n"
    prompt = (
        "You are an assistant. Use only the context sources to answer the question. "
        "Cite sources inline like [Source N]. If the answer is not in the context, say 'I don't know'.\n\n"
        f"CONTEXT:{ctx}\n\nQUESTION: {query}\n\nAnswer concisely with citations:"
    )
    return prompt

def answer_query(query: str, top_k: int = 20, use_openai: bool = False, openai_client = None) -> Dict[str, Any]:
    """
    High-level flow:
     - embed query and search FAISS (top_k)
     - rerank by keyword boosts
     - attempt specialized extractions (comparison, numeric, repurchase, certification)
     - if found -> return concise extracted answer + citation
     - else -> assemble prompt with top chunks and generate answer via local generator (or openai if configured)
    Returns dict with keys: answer (str), method (extract/generate), citations (list of chunks), retrieved (top chunks)
    """
    # embed + retrieve
    q_emb = embed_texts([query])
    try:
        results, scores = search_index(q_emb, top_k=top_k)
    except Exception as e:
        raise RuntimeError(f"Index search failed: {e}")

    # 2) rerank using keyword boosts + base scores
    ranked = rerank_by_keyword(results, base_scores=scores)
    best_chunks = [r[0] for r in ranked]  # ordered highest->lowest

    # normalize query lowercase for heuristics
    q_lower = (query or "").strip().lower()

    # ---------- 3) Comparison extraction (e.g., "compare", "vs", "how did X compare") ----------
    is_comparison = bool(re.search(r"\b(compare|vs|versus|compared to|how did)\b", q_lower))
    if is_comparison:
        primary_labels = ["revenue", "total revenue", "net revenue"]
        for lab in primary_labels:
            cur, pri, cchunk = extract_comparison_from_chunks(best_chunks[:max(20, top_k)], lab)
            if cur and pri:
                answer_text = f"${cur} (current) vs ${pri} (prior) — source: {cchunk.get('doc_id')} page {cchunk.get('page')}"
                citation = {"doc_id": cchunk.get('doc_id'), "page": cchunk.get('page'), "chunk_id": cchunk.get('chunk_id'), "label": lab}
                return {
                    "answer": answer_text,
                    "method": "extraction_comparison",
                    "citation": citation,
                    "retrieved": best_chunks[:min(len(best_chunks), 20)]
                }

    # ---------- 4) Repurchase / buyback extraction ----------
    if any(tok in q_lower for tok in ["repurchase", "repurchased", "buyback", "share repurchase", "shares repurchased"]):
        rep_val, rep_chunk = extract_repurchases(best_chunks[:max(30, top_k)])
        if rep_val:
            answer_text = f"{rep_val} (from {rep_chunk.get('doc_id')} page {rep_chunk.get('page')})"
            return {
                "answer": answer_text,
                "method": "repurchase_extraction",
                "citation": {"doc_id": rep_chunk.get('doc_id'), "page": rep_chunk.get('page'), "chunk_id": rep_chunk.get('chunk_id')},
                "retrieved": best_chunks[:min(len(best_chunks), 30)]
            }

    # ---------- 5) Certification / exhibit extraction ----------
    if any(tok in q_lower for tok in ["certification", "certifications", "certify", "certified", "exhibit 32", "exhibit 101"]):
        cert_text, cert_chunk = extract_certification_text(best_chunks[:max(40, top_k)])
        if cert_text:
            short = cert_text if len(cert_text) < 1200 else cert_text[:1200] + "..."
            return {
                "answer": short,
                "method": "cert_extraction",
                "citation": {"doc_id": cert_chunk.get('doc_id'), "page": cert_chunk.get('page'), "chunk_id": cert_chunk.get('chunk_id')},
                "retrieved": best_chunks[:min(len(best_chunks), 40)]
            }

    # ---------- 6) Try numeric extraction for common numeric labels ----------
    numeric_labels = [
        "total revenue", "revenue", "cost of revenue", "net income",
        "cash and cash equivalents", "basic net income per share",
        "diluted net income per share", "earnings per share", "eps", "total assets",
        "total liabilities"
    ]
    val, chunk, label = extract_numeric_candidates_from_chunks(best_chunks[:max(12, top_k)], numeric_labels)
    if val:
        answer_text = f"${val} (from {chunk.get('doc_id')} page {chunk.get('page')})"
        citation = {"doc_id": chunk.get('doc_id'), "page": chunk.get('page'), "chunk_id": chunk.get('chunk_id'), "label": label}
        return {
            "answer": answer_text,
            "method": "extraction_single_numeric",
            "citation": citation,
            "retrieved": best_chunks[:min(len(best_chunks), 12)]
        }

    # ---------- 7) Fallback: generative answer using grounded prompt ----------
    # Build a concise prompt with top chunks
    prompt_chunks = best_chunks[:6]
    # If the question seems like it wants a short numeric answer, use numeric prompt; else general prompt
    wants_numeric = bool(re.search(r"\b(how many|what is the total|what was|how much|amount|value)\b", q_lower))
    if wants_numeric:
        prompt = assemble_numeric_prompt(query, prompt_chunks)
    else:
        prompt = assemble_prompt(query, prompt_chunks)

    if use_openai and openai_client:
        # using OpenAI (caller must pass configured client)
        resp = openai_client.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=256,
            temperature=0.0
        )
        out = resp.choices[0].text.strip()
    else:
        # local generator fallback
        gen = get_local_generator()
        # generate; adjust max_length to control verbosity
        try:
            gen_out = gen(prompt, max_length=256, do_sample=False)
            out = gen_out[0].get("generated_text", "").strip()
        except Exception as e:
            # graceful fallback message
            out = f"Generation failed: {e}"

    citations = [
        {"doc_id": c.get("doc_id"), "page": c.get("page"), "chunk_id": c.get("chunk_id")}
        for c in prompt_chunks
    ]
    return {
        "answer": out,
        "method": "generation",
        "citations": citations,
        "retrieved": best_chunks[:min(len(best_chunks), 20)],
        "prompt": prompt
    }

