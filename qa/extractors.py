import re
from typing import List, Tuple, Optional

_money_with_commas_or_dollar = re.compile(
    r"(?:\$\s*)?([0-9]{1,3}(?:,[0-9]{3})+(?:\.\d+)?|(?:\$\s*)[0-9]{4,}(?:\.\d+)?)"
)
_loose_number = re.compile(r"\(?\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?|[0-9]{1,})(?:\s*(million|billion))?\)?", re.IGNORECASE)

_percent_pat = re.compile(r"([0-9]{1,3}(?:\.\d+)?)\s*%")
_two_numbers_line = re.compile(
    r"(?:\$?\s*)([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?|[0-9]{4,}(?:\.\d+)?)(?:\D{1,6})+([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?|[0-9]{4,}(?:\.\d+)?)"
)

_label_money_hint = re.compile(r"(revenue|cost of revenue|net income|cash and cash equivalents|total assets|total liabilities|eps|earnings per share)", re.IGNORECASE)
_repurch_row_keywords = ["repurchase", "repurchased", "buyback", "shares repurchased", "share repurchase"]

def _clean_text_dedupe(text: str, max_repeat_seq_len: int = 80) -> str:
    """Remove immediate duplicated blocks often produced by OCR."""
    if not text:
        return text
    t = re.sub(r'\s+', ' ', text).strip()
    # naive de-dup: if start repeats, collapse repeats
    for L in range(10, min(max_repeat_seq_len, len(t)//2 + 1), 10):
        sub = t[:L]
        if sub and t.startswith(sub*2):
            while t.startswith(sub*2):
                t = t[len(sub):]
            t = t.strip()
    return t

def _parse_number(token: str) -> Optional[float]:
    """
    Parse numeric token like "26,044", "$26,044", "(26,044)", "26 million".
    Returns numeric value in plain number (no unit conversion except million/billion).
    """
    if not token:
        return None
    t = token.strip()
    # detect million/billion
    m_unit = re.search(r"(million|billion)", t, re.IGNORECASE)
    unit = 1.0
    if m_unit:
        if m_unit.group(1).lower() == "million":
            unit = 1e6
        elif m_unit.group(1).lower() == "billion":
            unit = 1e9
        # remove unit from string for parsing
        t = re.sub(r"(million|billion)", "", t, flags=re.IGNORECASE).strip()
    # remove $ and surrounding parentheses
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1].strip()
    t = t.replace("$", "").replace(",", "").replace(" ", "")
    try:
        val = float(t)
        val = val * unit
        if neg:
            val = -val
        return val
    except Exception:
        return None

def _select_best_money_candidate(candidates: List[str]) -> Optional[str]:

    if not candidates:
        return None
    parsed = []
    for c in candidates:
        p = _parse_number(c)
        if p is not None:
            parsed.append((c, p))
    if not parsed:
        return None
    # preferred ones: those that originally matched _money_with_commas_or_dollar OR contained '$' or ','
    preferred = [t for t, v in parsed if ('$' in t) or (',' in t)]
    if preferred:
        # choose the preferred one with largest absolute value
        best = max([(t, _parse_number(t)) for t in preferred], key=lambda x: abs(x[1]))
        return best[0]
    # else return the largest numeric by absolute value
    best = max(parsed, key=lambda x: abs(x[1]))
    return best[0]

def extract_first_money_after_label(text: str, label: str) -> Optional[str]:
    """
    Search for label and return the most likely monetary candidate found nearby.
    """
    if not text:
        return None
    txt = text.replace("\r", "\n")
    lines = txt.split("\n")
    label_l = label.lower()
    # look for lines containing label
    for i, ln in enumerate(lines):
        if label_l in ln.lower():
            # 1) try two numbers in same line
            two = _two_numbers_line.search(ln)
            if two:
                return two.group(1)
            # 2) look for strict money candidates in the same line
            cands = _money_with_commas_or_dollar.findall(ln)
            if cands:
                return _select_best_money_candidate(cands)
            loose = []
            for j in range(0, 3):
                if i + j < len(lines):
                    l2 = lines[i + j]
                    # skip percentages
                    if _percent_pat.search(l2):
                        continue
                    for m in _loose_number.finditer(l2):
                        num_str = m.group(0)
                        loose.append(num_str)
            if loose:
                # prefer best loose candidate
                return _select_best_money_candidate(loose)
    # fallback: search entire text for strict money pattern
    all_cands = _money_with_commas_or_dollar.findall(txt)
    if all_cands:
        return _select_best_money_candidate(all_cands)
    # last resort: any loose number
    all_loose = [m.group(0) for m in _loose_number.finditer(txt) if not _percent_pat.search(m.group(0))]
    if all_loose:
        return _select_best_money_candidate(all_loose)
    return None

def extract_two_period_values_from_row(text: str, label_hint: str = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:

    if not text:
        return None, None, None
    txt = text.replace("\r", "\n")
    lines = txt.split("\n")
    for ln in lines:
        if label_hint and label_hint.lower() not in ln.lower():
            continue
        m = _two_numbers_line.search(ln)
        if m:
            return m.group(1), m.group(2), ln
    for ln in lines:
        # find money-with-commas tokens
        strict = _money_with_commas_or_dollar.findall(ln)
        if len(strict) >= 2:
            return strict[0], strict[1], ln
        # loose fallback
        loose = [m.group(0) for m in _loose_number.finditer(ln) if not _percent_pat.search(m.group(0))]
        if len(loose) >= 2:
            # pick two best candidates
            v1 = _select_best_money_candidate([loose[0]])
            v2 = _select_best_money_candidate([loose[1]])
            return v1, v2, ln
    return None, None, None

def extract_numeric_candidates_from_chunks(chunks: List[dict], labels: List[str]):
    """
    Given list of chunks and labels, return the first found numeric value and the chunk that contained it.
    Prefers chunks whose 'type' is 'table_row' or contains the label text.
    """
    for label in labels:
        for c in chunks:
            text = c.get("text","") or ""
            if c.get("type","").lower().startswith("table") and label.lower() in text.lower():
                val = extract_first_money_after_label(text, label=label)
                if val:
                    return val, c, label
    
    for label in labels:
        for c in chunks:
            text = c.get("text","") or ""
            if label.lower() in text.lower():
                val = extract_first_money_after_label(text, label=label)
                if val:
                    return val, c, label
    # finally try any chunk, prefer table_row chunks
    for c in chunks:
        text = c.get("text","") or ""
        val = extract_first_money_after_label(text, label=labels[0] if labels else "")
        if val:
            return val, c, labels[0] if labels else None
    return None, None, None


# ----- Add this function to qa/extractors.py -----
def extract_comparison_from_chunks(chunks: List[dict], label_hint: str = None) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
    if not chunks:
        return None, None, None

    # Prefer table rows that include the label
    if label_hint:
        for c in chunks:
            if not c:
                continue
            ctype = c.get("type", "").lower()
            text = c.get("text", "") or ""
            if ctype.startswith("table") and label_hint.lower() in text.lower():
                cur, pri, ln = extract_two_period_values_from_row(text, label_hint=label_hint)
                if cur and pri:
                    return cur, pri, c

    # Any chunk that contains the label
    if label_hint:
        for c in chunks:
            if not c:
                continue
            text = c.get("text", "") or ""
            if label_hint.lower() in text.lower():
                cur, pri, ln = extract_two_period_values_from_row(text, label_hint=label_hint)
                if cur and pri:
                    return cur, pri, c

    # Fallback: try all table_row chunks for any two-number pattern 
    for c in chunks:
        if not c:
            continue
        ctype = c.get("type", "").lower()
        text = c.get("text", "") or ""
        if ctype.startswith("table"):
            cur, pri, ln = extract_two_period_values_from_row(text, label_hint=None)
            if cur and pri:
                
                if label_hint and label_hint.lower() not in text.lower():
                    
                    return cur, pri, c
                else:
                    return cur, pri, c

    # Last resort: scan all chunks for any line with two money-like tokens
    for c in chunks:
        if not c:
            continue
        text = c.get("text", "") or ""
        cur, pri, ln = extract_two_period_values_from_row(text, label_hint=None)
        if cur and pri:
            return cur, pri, c

    return None, None, None
# ----- end of addition -----



def extract_repurchases(chunks: List[dict]):
    """
    Search for repurchase-related lines and try to return either monetary or share amounts.
    
    """
    for c in chunks:
        text = (c.get("text","") or "").lower()
        if any(k in text for k in _repurch_row_keywords):
            # try strict money first
            strict = _money_with_commas_or_dollar.findall(text)
            if strict:
                return _select_best_money_candidate(strict), c
            # try loose numbers with shares
            m2 = re.search(r"([0-9]{1,3}(?:,[0-9]{3})*)\s+shares", text)
            if m2:
                return m2.group(1) + " shares", c
            # else return a cleaned snippet
            snippet = _clean_text_dedupe(text[:400])
            return snippet, c
    return None, None, None

def extract_certification_text(chunks: List[dict]):
    """
    Look for certification / exhibit text blocks and return cleaned paragraph + chunk.
    """
    candidates = []
    for c in chunks:
        txt = c.get("text","") or ""
        if 'certificat' in txt.lower() or 'exhibit' in txt.lower() or 'furnished' in txt.lower():
            cleaned = _clean_text_dedupe(txt)
            candidates.append((cleaned, c))
    if candidates:
        candidates.sort(key=lambda x: len(x[0]), reverse=True)
        return candidates[0]
    return None, None, None
