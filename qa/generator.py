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

# def answer_query(query: str, top_k: int = 20, use_openai: bool = False, openai_client = None) -> dict:
#     """
#     Hybrid retrieval + extraction + generation pipeline.

#     Steps:
#       - Embed query and search FAISS
#       - Load BM25 and run BM25 search (if available)
#       - Fuse FAISS + BM25 via Reciprocal Rank Fusion (RRF)
#       - Run keyword reranker as fallback if BM25 missing
#       - Run specialized extractors (comparison, numeric, repurchase, certification)
#       - If extraction succeeds return concise answer + citation
#       - Else assemble grounded prompt and generate answer (local or OpenAI)
#     Returns:
#       dict with keys:
#         - answer: str
#         - method: str
#         - citations: list (concise)
#         - retrieved: list of chunk dicts (with snippet and possible rrf_score)
#         - prompt: str (present when generation used)
#     """
#     # local imports to make this function drop-in friendly
#     import re, pickle, os
#     from typing import List, Dict, Any
#     from embeddings.embedder import embed_texts
#     from index.faiss_index import search_index, META_PATH
#     # BM25 imports (will raise if module missing - handled below)
#     try:
#         from index.bm25_index import load_bm25_index, bm25_search
#         bm25_available = True
#     except Exception:
#         bm25_available = False
#         load_bm25_index = None
#         bm25_search = None

#     # reranker + rrf
#     try:
#         from qa.rerank import rerank_by_keyword, reciprocal_rank_fusion
#     except Exception:
#         # fallback minimal reranker
#         def rerank_by_keyword(chunks, base_scores=None):
#             return [(c, (base_scores[i] if base_scores else 0.0)) for i, c in enumerate(chunks)]
#         def reciprocal_rank_fusion(a, b, k=60, weight_faiss=1.0, weight_bm25=1.0):
#             # simplest fallback: return FAISS order
#             return [ {"chunk": r.get("chunk") if isinstance(r, dict) and r.get("chunk") is not None else r} for r in a ]

#     # extractors
#     from qa.extractors import (
#         extract_numeric_candidates_from_chunks,
#         extract_comparison_from_chunks,
#         extract_repurchases,
#         extract_certification_text
#     )

#     # local generator helper
#     try:
#         from transformers import pipeline
#         _local_gen = None
#         def get_local_generator():
#             nonlocal _local_gen
#             if _local_gen is None:
#                 _local_gen = pipeline("text2text-generation", model="google/flan-t5-small", device=-1)
#             return _local_gen
#     except Exception:
#         # if transformers not available, set to None and handle later
#         def get_local_generator():
#             raise RuntimeError("Local generator (transformers) not available. Install transformers and a model.")

#     # prompt assembly helpers
#     def assemble_numeric_prompt(q: str, top_chunks: List[Dict[str,Any]]) -> str:
#         ctx = ""
#         for i, r in enumerate(top_chunks, 1):
#             snippet = r.get("text","")
#             ctx += f"\n[Source {i}] (doc:{r.get('doc_id')} page:{r.get('page')} type:{r.get('type')})\n{snippet}\n"
#         prompt = (
#             "You are an assistant. The user asked for a numeric fact. Use ONLY the context sources below to find the exact numeric value. "
#             "Return ONE short sentence with the number and a citation in brackets like: \"$26,044 [Source 1]\". "
#             "If the number is not present exactly in the context, say 'Not found in context'.\n\n"
#             f"CONTEXT:{ctx}\n\nQUESTION: {q}\n\nAnswer:"
#         )
#         return prompt

#     def assemble_prompt(q: str, top_chunks: List[Dict[str,Any]]) -> str:
#         ctx = ""
#         for i, r in enumerate(top_chunks, 1):
#             ctx += f"\n[Source {i}] (doc:{r.get('doc_id')} page:{r.get('page')} type:{r.get('type')})\n{r.get('text','')}\n"
#         prompt = (
#             "You are an assistant. Use only the context sources to answer the question. "
#             "Cite sources inline like [Source N]. If the answer is not in the context, say 'I don't know'.\n\n"
#             f"CONTEXT:{ctx}\n\nQUESTION: {q}\n\nAnswer concisely with citations:"
#         )
#         return prompt

#     # ---------- Retrieval: FAISS ----------
#     # Embed the query
#     try:
#         q_emb = embed_texts([query])
#     except Exception as e:
#         raise RuntimeError(f"Failed to embed query: {e}")

#     try:
#         faiss_results, faiss_scores = search_index(q_emb, top_k=top_k)
#     except Exception as e:
#         raise RuntimeError(f"FAISS search failed: {e}")

#     # Ensure faiss_results is list of chunks and faiss_scores is list of floats
#     if not isinstance(faiss_results, list):
#         raise RuntimeError("FAISS search returned unexpected result format.")

#     # Wrap FAISS hits as [{'chunk':..., 'score':..., 'rank':...}, ...]
#     faiss_wrapped = []
#     for i, (chunk, score) in enumerate(zip(faiss_results, faiss_scores), start=1):
#         # attach base faiss score to chunk for UI convenience
#         if isinstance(chunk, dict):
#             chunk = dict(chunk)  # shallow copy to avoid mutating original
#         chunk.setdefault("score", float(score))
#         faiss_wrapped.append({"chunk": chunk, "score": float(score), "rank": i})

#     # ---------- Retrieval: BM25 (optional) ----------
#     bm25_wrapped = []
#     full_chunks = None
#     if bm25_available:
#         try:
#             bm25_obj, tokenized = load_bm25_index()
#             # load full chunk list from meta (META_PATH)
#             try:
#                 with open(META_PATH, "rb") as f:
#                     full_chunks = pickle.load(f)
#             except Exception:
#                 # if meta cannot be loaded, use the chunks returned by FAISS as fallback
#                 full_chunks = [r["chunk"] for r in faiss_wrapped]
#             # run bm25 search
#             bm25_hits = bm25_search(bm25_obj, tokenized, full_chunks, query, top_n=top_k)
#             # bm25_hits: list of dicts {'chunk':..., 'score':..., 'rank':...}
#             for h in bm25_hits:
#                 c = h.get("chunk")
#                 if isinstance(c, dict):
#                     c = dict(c)
#                 bm25_wrapped.append({"chunk": c, "score": float(h.get("score", 0.0)), "rank": int(h.get("rank", 0))})
#         except FileNotFoundError:
#             bm25_wrapped = []
#         except Exception:
#             # If BM25 unexpectedly fails, ignore and proceed with FAISS-only
#             bm25_wrapped = []

#     # ---------- Fusion: RRF if BM25 present else FAISS-only rerank ----------
#     fused_chunks = []
#     if bm25_wrapped:
#         # use reciprocal_rank_fusion to combine faiss_wrapped & bm25_wrapped
#         try:
#             fused = reciprocal_rank_fusion(faiss_wrapped, bm25_wrapped, k=60, weight_faiss=1.0, weight_bm25=1.0)
#             # fused: list of {'chunk':..., 'rrf_score':...}
#             fused_chunks = []
#             for i, f in enumerate(fused, start=1):
#                 ch = dict(f.get("chunk", {}))
#                 ch["rrf_score"] = float(f.get("rrf_score", 0.0))
#                 ch["fused_rank"] = i
#                 fused_chunks.append(ch)
#             best_chunks = fused_chunks
#         except Exception:
#             # fallback to simple FAISS order
#             best_chunks = [r["chunk"] for r in faiss_wrapped]
#     else:
#         # no BM25 — fall back to keyword rerank on FAISS results
#         ranked = rerank_by_keyword([r["chunk"] for r in faiss_wrapped], base_scores=[r["score"] for r in faiss_wrapped])
#         # rerank_by_keyword expected to return list of tuples (chunk, combined_score)
#         try:
#             best_chunks = [r[0] for r in ranked]
#             # attach rerank score if present
#             for i, (chunk, combined) in enumerate(ranked, start=1):
#                 if isinstance(chunk, dict):
#                     chunk["rerank_score"] = float(combined)
#         except Exception:
#             best_chunks = [r["chunk"] for r in faiss_wrapped]

#     # ---------- Heuristics & extraction ----------
#     q_lower = (query or "").strip().lower()

#     # 1) Comparison queries
#     is_comparison = bool(re.search(r"\b(compare|vs|versus|compared to|how did)\b", q_lower))
#     if is_comparison:
#         primary_labels = ["revenue", "total revenue", "net revenue"]
#         for lab in primary_labels:
#             cur, pri, cchunk = extract_comparison_from_chunks(best_chunks[:max(20, top_k)], lab)
#             if cur and pri:
#                 answer_text = f"${cur} (current) vs ${pri} (prior) — source: {cchunk.get('doc_id')} page {cchunk.get('page')}"
#                 citation = {"doc_id": cchunk.get('doc_id'), "page": cchunk.get('page'), "chunk_id": cchunk.get('chunk_id'), "label": lab}
#                 return {
#                     "answer": answer_text,
#                     "method": "extraction_comparison",
#                     "citation": citation,
#                     "retrieved": best_chunks[:min(len(best_chunks), 20)]
#                 }

#     # 2) Repurchase / buyback extraction
#     if any(tok in q_lower for tok in ["repurchase", "repurchased", "buyback", "share repurchase", "shares repurchased"]):
#         rep_val, rep_chunk = extract_repurchases(best_chunks[:max(30, top_k)])
#         if rep_val:
#             answer_text = f"{rep_val} (from {rep_chunk.get('doc_id')} page {rep_chunk.get('page')})"
#             return {
#                 "answer": answer_text,
#                 "method": "repurchase_extraction",
#                 "citation": {"doc_id": rep_chunk.get('doc_id'), "page": rep_chunk.get('page'), "chunk_id": rep_chunk.get('chunk_id')},
#                 "retrieved": best_chunks[:min(len(best_chunks), 30)]
#             }

#     # 3) Certification/exhibit extraction
#     if any(tok in q_lower for tok in ["certification", "certifications", "certify", "certified", "exhibit 32", "exhibit 101"]):
#         cert_text, cert_chunk = extract_certification_text(best_chunks[:max(40, top_k)])
#         if cert_text:
#             short = cert_text if len(cert_text) < 1200 else cert_text[:1200] + "..."
#             return {
#                 "answer": short,
#                 "method": "cert_extraction",
#                 "citation": {"doc_id": cert_chunk.get('doc_id'), "page": cert_chunk.get('page'), "chunk_id": cert_chunk.get('chunk_id')},
#                 "retrieved": best_chunks[:min(len(best_chunks), 40)]
#             }

#     # 4) Single numeric extraction
#     numeric_labels = [
#         "total revenue", "revenue", "cost of revenue", "net income",
#         "cash and cash equivalents", "basic net income per share",
#         "diluted net income per share", "earnings per share", "eps", "total assets",
#         "total liabilities"
#     ]
#     val, chunk, label = extract_numeric_candidates_from_chunks(best_chunks[:max(12, top_k)], numeric_labels)
#     if val:
#         answer_text = f"${val} (from {chunk.get('doc_id')} page {chunk.get('page')})"
#         citation = {"doc_id": chunk.get('doc_id'), "page": chunk.get('page'), "chunk_id": chunk.get('chunk_id'), "label": label}
#         return {
#             "answer": answer_text,
#             "method": "extraction_single_numeric",
#             "citation": citation,
#             "retrieved": best_chunks[:min(len(best_chunks), 12)]
#         }

#     # ---------- Fallback: generative answer ----------
#     # choose prompt style
#     prompt_chunks = best_chunks[:6]
#     wants_numeric = bool(re.search(r"\b(how many|what is the total|what was|how much|amount|value)\b", q_lower))
#     if wants_numeric:
#         prompt = assemble_numeric_prompt(query, prompt_chunks)
#     else:
#         prompt = assemble_prompt(query, prompt_chunks)

#     # call LLM (OpenAI if configured else local)
#     out = ""
#     if use_openai and openai_client:
#         try:
#             resp = openai_client.Completion.create(engine="text-davinci-003", prompt=prompt, max_tokens=256, temperature=0.0)
#             out = resp.choices[0].text.strip()
#         except Exception as e:
#             out = f"OpenAI generation failed: {e}"
#     else:
#         try:
#             gen = get_local_generator()
#             gen_out = gen(prompt, max_length=256, do_sample=False)
#             out = gen_out[0].get("generated_text", "").strip()
#         except Exception as e:
#             out = f"Local generation failed: {e}"

#     # prepare citation list (concise)
#     citations = []
#     for c in prompt_chunks:
#         citations.append({"doc_id": c.get("doc_id"), "page": c.get("page"), "chunk_id": c.get("chunk_id")})

#     # return generation response (include prompt for dev debugging)
#     return {
#         "answer": out,
#         "method": "generation",
#         "citations": citations,
#         "retrieved": best_chunks[:min(len(best_chunks), 20)],
#         "prompt": prompt
#     }




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
    # 1) embed + retrieve
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



# def answer_query(query: str, top_k: int = 20, use_openai=False, openai_client=None):
#     """
#     High-level flow:
#      - embed query and search FAISS (top_k)
#      - rerank by keyword boosts
#      - attempt numeric extraction (for numeric style queries) using labels
#      - if found -> return concise numeric answer + citation
#      - else -> assemble prompt with top chunks and generate answer via local generator (or openai if configured)
#     Returns dict with keys: answer (str), method (extract/generate), citations (list of chunks)
#     """
#     # 1) retrieve
#     q_emb = embed_texts([query])
#     try:
#         results, scores = search_index(q_emb, top_k=top_k)
#     except Exception as e:
#         # propagate readable error for UI
#         raise RuntimeError(f"Index search failed: {e}")

#     # 2) rerank
#     ranked = rerank_by_keyword(results, base_scores=scores)
#     best_chunks = [r[0] for r in ranked]

#     # 3) Try numeric extraction for common numeric labels
#     numeric_labels = ["total revenue", "revenue", "cost of revenue", "net income", "cash and cash equivalents", "basic net income per share", "diluted net income per share", "earnings per share", "eps"]
#     val, chunk, label = extract_numeric_candidates_from_chunks(best_chunks[:12], numeric_labels)
#     if val:
#         # format answer
#         answer_text = f"${val} (from {chunk.get('doc_id')} page {chunk.get('page')})"
#         citation = {"doc_id": chunk.get('doc_id'), "page": chunk.get('page'), "chunk_id": chunk.get('chunk_id'), "label": label}
#         return {"answer": answer_text, "method":"extraction", "citation": citation, "retrieved": best_chunks[:8]}

#     # 4) fallback: generate using local LLM with strict prompt for grounding
#     prompt = assemble_numeric_prompt(query, best_chunks[:6])
#     if use_openai and openai_client:
#         resp = openai_client.Completion.create(engine="text-davinci-003", prompt=prompt, max_tokens=128, temperature=0.0)
#         out = resp.choices[0].text.strip()
#     else:
#         gen = get_local_generator()
#         out = gen(prompt, max_length=128, do_sample=False)[0]["generated_text"].strip()

#     # 5) return with citations (top chunks used)
#     citations = [{"doc_id": c.get("doc_id"), "page": c.get("page"), "chunk_id": c.get("chunk_id")} for c in best_chunks[:6]]
#     return {"answer": out, "method":"generation", "citations": citations, "retrieved": best_chunks[:8]}



# def retrieve(query, top_k=5):
#     q_emb = embed_texts([query])
#     results, scores = search_index(q_emb, top_k=top_k)
#     return results, scores

# def assemble_prompt(query, retrieved_chunks):
#     ctx = ""
#     for i, r in enumerate(retrieved_chunks, 1):
#         s = r.get("text", "")
#         ctx += f"\n[Source {i}] (doc:{r.get('doc_id')} page:{r.get('page')} type:{r.get('type')})\n{s}\n"
#     prompt = (
#         "You are an assistant. Use only the context sources to answer the question. "
#         "Cite the sources inline like [Source 1]. If the answer is not in the context, say 'I don't know'.\n\n"
#         f"CONTEXT:{ctx}\n\nQUESTION: {query}\n\nAnswer concisely with citations:"
#     )
#     return prompt

# def generate_answer(prompt, use_openai=False, openai_client=None, max_tokens=256):
#     """
#     If use_openai True, expects openai_client (openai module initialized).
#     Otherwise uses local flan-t5-small.
#     """
#     if use_openai and openai_client:
#         resp = openai_client.Completion.create(
#             engine="text-davinci-003",
#             prompt=prompt,
#             max_tokens=max_tokens,
#             temperature=0.0
#         )
#         return resp.choices[0].text.strip()
#     else:
#         gen = get_local_generator()
#         out = gen(prompt, max_length= max_tokens, do_sample=False)
#         return out[0]['generated_text'].strip()
