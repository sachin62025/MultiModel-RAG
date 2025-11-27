# qa/rerank.py 
import re

KEYWORD_BOOSTS = [
    "revenue", "net revenue", "total revenue", "condensed consolidated statements",
    "condensed consolidated statements of income", "cost of revenue", "net income",
    "cash and cash equivalents", "operating income", "eps", "earnings per share", "balance sheet"
]

def keyword_score(text):
    t = (text or "").lower()
    score = 0.0
    for kw in KEYWORD_BOOSTS:
        if kw in t:
            score += 1.0
    if re.search(r"(revenue|net income|cost of revenue|cash)\s*[\$:]{0,1}\s*[0-9]{1,3}(?:,[0-9]{3})+", t):
        score += 2.0
    return float(score)

def rerank_by_keyword(retrieved_chunks, base_scores=None):
    out = []
    for idx, c in enumerate(retrieved_chunks):
        b = float(base_scores[idx]) if base_scores is not None else 0.0
        k = keyword_score(c.get("text", ""))
        combined = b + 2.0 * k
        out.append((c, combined))
    out.sort(key=lambda x: x[1], reverse=True)
    return out
