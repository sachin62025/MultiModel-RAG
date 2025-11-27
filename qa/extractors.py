# # qa/extractors.py
# import re

# _money_pat = re.compile(r"(?:\$|\b)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?)\b(?!\s*%)")
# _percent_pat = re.compile(r"([0-9]{1,3}(?:\.\d+)?)\s*%")
# _two_numbers_line = re.compile(
#     r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?)\D+([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?)"
# )

# _revenue_row = re.compile(r"revenue", re.IGNORECASE)
# _repurch_row_keywords = ["repurchase", "repurchased", "share repurchase", "shares repurchased", "buyback", "repurchase of common stock"]


# def _clean_text_dedupe(text: str, max_repeat_seq_len: int = 80):
#     """
#     Remove immediate repeated phrases (OCR or extraction can duplicate headings).
#     Simple heuristic: find repeated contiguous substrings and truncate duplicates.
#     """
#     if not text:
#         return text
#     # collapse repeated whitespace
#     t = re.sub(r'\s+', ' ', text).strip()
#     # naive dedupe: if a substring repeats two or more times consecutively, shorten to one
#     # check for repeating segments of up to max_repeat_seq_len chars
#     for L in range(10, max_repeat_seq_len, 10):
#         if len(t) > 2*L:
#             sub = t[:L]
#             # if the start repeats immediately, cut duplicates
#             if t.startswith(sub*2):
#                 # remove extra repeats
#                 while t.startswith(sub*2):
#                     t = t[len(sub):]
#                 t = t.strip()
#     return t

# def extract_first_money_after_label(text: str, label: str):
#     """
#     Search for the label and return the first non-percentage monetary value found on the same or following lines.
#     """
#     if not text:
#         return None
#     txt = text.replace("\r", "\n")
#     lines = txt.split("\n")
#     label_l = label.lower()
#     for i, ln in enumerate(lines):
#         if label_l in ln.lower():
#             # try to match two numbers on same line
#             two = _two_numbers_line.search(ln)
#             if two:
#                 return two.group(1)  # return first (current) by default
#             # else find first money not followed by % on same line
#             m = _money_pat.search(ln)
#             if m:
#                 return m.group(1)
#             # try the next two lines
#             for j in range(1, 3):
#                 if i + j < len(lines):
#                     l2 = lines[i + j]
#                     if _percent_pat.search(l2):
#                         # skip lines that are just percentages
#                         continue
#                     m2 = _money_pat.search(l2)
#                     if m2:
#                         return m2.group(1)
#     # fallback: search for first money not part of a percent anywhere
#     m_any = _money_pat.search(txt)
#     if m_any:
#         return m_any.group(1)
#     return None

# def extract_two_period_values_from_row(text: str, label_hint: str = None):
#     """
#     Attempt to extract two adjacent monetary values for current and prior periods from a single table row or line.
#     Returns (value_current, value_prior, chunk_line) or (None, None, None)
#     """
#     if not text:
#         return None, None, None
#     txt = text.replace("\r", "\n")
#     # look for lines containing the label_hint if provided
#     lines = txt.split("\n")
#     for ln in lines:
#         if label_hint and label_hint.lower() not in ln.lower():
#             continue
#         # try to find two numbers
#         m = _two_numbers_line.search(ln)
#         if m:
#             return m.group(1), m.group(2), ln
#     # fallback: search entire text for a line that contains two numbers close together
#     for ln in lines:
#         m = _two_numbers_line.search(ln)
#         if m:
#             return m.group(1), m.group(2), ln
#     return None, None, None

# def extract_numeric_candidates_from_chunks(chunks: list, labels: list):
#     """
#     Given list of chunks and labels, return the first found numeric value and the chunk that contained it.
#     This prefers exact label matches and avoids percentages.
#     """
#     for label in labels:
#         for c in chunks:
#             text = c.get("text","")
#             val = extract_first_money_after_label(text, label=label)
#             if val:
#                 return val, c, label
#     return None, None, None

# def extract_comparison_from_chunks(chunks: list, label: str):
#     """
#     Try to extract both current and prior values for label (e.g., 'revenue').
#     Returns (cur_val, prior_val, chunk_where_found) or (None, None, None)
#     """
#     # 1) Look for a table row with two numbers on same line
#     for c in chunks:
#         text = c.get("text","")
#         cur, pri, ln = extract_two_period_values_from_row(text, label_hint=label)
#         if cur and pri:
#             return cur, pri, c
#     # 2) If not found, try to get two separate values by searching 'Apr' headings or nearby tokens (less reliable)
#     # Try to find the first chunk that includes label and then parse next numbers
#     for c in chunks:
#         text = c.get("text","")
#         if label.lower() in text.lower():
#             # find all money matches in chunk (excluding percentages)
#             vals = _money_pat.findall(text)
#             if len(vals) >= 2:
#                 return vals[0], vals[1], c
#     return None, None, None

# def extract_repurchases(chunks: list):
#     """
#     Search for repurchase-related lines and try to return either monetary or share amounts.
#     Returns (description, chunk) or (None, None)
#     """
#     for c in chunks:
#         text = c.get("text","").lower()
#         # prefer rows that contain repurchase keywords
#         if any(k in text for k in _repurch_row_keywords):
#             # try to extract money first
#             m = _money_pat.search(text)
#             if m:
#                 return m.group(1), c
#             # try to extract shares (e.g., 'X shares repurchased')
#             m2 = re.search(r"([0-9]{1,3}(?:,[0-9]{3})*)\s+shares", text)
#             if m2:
#                 return m2.group(1) + " shares", c
#             # else return small descriptive snippet
#             snippet = text[:400]
#             snippet = _clean_text_dedupe(snippet)
#             return snippet, c
#     return None, None, None

# def extract_certification_text(chunks: list):
#     """
#     Look for chunks mentioning 'certification' or 'exhibit' and return cleaned paragraphs.
#     """
#     candidates = []
#     for c in chunks:
#         txt = c.get("text","")
#         if 'certificat' in txt.lower() or 'exhibit' in txt.lower() or 'certification' in txt.lower():
#             cleaned = _clean_text_dedupe(txt)
#             candidates.append((cleaned, c))
#     # return the chunk with the longest cleaned text (likely the full certification block)
#     if candidates:
#         candidates.sort(key=lambda x: len(x[0]), reverse=True)
#         return candidates[0]
#     return None, None, None



# # def extract_first_money_after_label(text: str, label: str):
# #     """
# #     Search for the label in the text and return the first monetary value found
# #     on the same or following lines. Returns a normalized string like '26,044' or None.
# #     """
# #     if not text:
# #         return None
# #     txt = text.replace("\r", "\n")
# #     lines = txt.split("\n")
# #     for i, ln in enumerate(lines):
# #         if label.lower() in ln.lower():
# #             m = _money_pat.search(ln)
# #             if m:
# #                 return m.group(1)
# #             # try following lines
# #             for j in range(1, 3):
# #                 if i + j < len(lines):
# #                     m2 = _money_pat.search(lines[i + j])
# #                     if m2:
# #                         return m2.group(1)
# #     # fallback: find a revenue-like row anywhere
# #     m_row = _revenue_row.search(txt)
# #     if m_row:
# #         m = _money_pat.search(m_row.group(0))
# #         if m:
# #             return m.group(1)
# #     return None

# # def extract_numeric_candidates_from_chunks(chunks: list, labels: list):
# #     """
# #     Given a list of chunks, returns the first found numeric value and the chunk that contained it.
# #     labels: list[str] of labels to try (e.g., ["revenue","cost of revenue"])
# #     """
# #     for label in labels:
# #         for c in chunks:
# #             val = extract_first_money_after_label(c.get("text",""), label=label)
# #             if val:
# #                 return val, c, label
# #     # no match
# #     return None, None, None


# qa/extractors.py
import re
from typing import List, Tuple, Optional

_money_with_commas_or_dollar = re.compile(
    r"(?:\$\s*)?([0-9]{1,3}(?:,[0-9]{3})+(?:\.\d+)?|(?:\$\s*)[0-9]{4,}(?:\.\d+)?)"
)

# Loose numeric pattern (fallback) - captures any digit sequence
_loose_number = re.compile(r"\(?\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?|[0-9]{1,})(?:\s*(million|billion))?\)?", re.IGNORECASE)

# detect explicit percent to avoid treating percent values as money
_percent_pat = re.compile(r"([0-9]{1,3}(?:\.\d+)?)\s*%")

# two numbers on one line (current vs prior), more robust
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
    """
    Given a list of numeric string candidates from a chunk, choose the best:
      1) Prefer ones that had a '$' or comma
      2) Then the largest numeric value
    Returns the original candidate string (not parsed) or None.
    """
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
                # return first (current)
                return two.group(1)
            # 2) look for strict money candidates in the same line
            cands = _money_with_commas_or_dollar.findall(ln)
            if cands:
                # the regex returns groups so join results
                # cands may be list of strings
                return _select_best_money_candidate(cands)
            # 3) look for all loose numbers on same line and next two lines
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
    """
    Try to extract two adjacent monetary values for current and prior periods from a single table row or line.
    Returns (value_current, value_prior, chunk_line) or (None, None, None)
    """
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
    # fallback: look for any line with two money-like tokens (with commas or $) within close proximity
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
    # prioritize table_row chunks that contain the label
    for label in labels:
        for c in chunks:
            text = c.get("text","") or ""
            if c.get("type","").lower().startswith("table") and label.lower() in text.lower():
                val = extract_first_money_after_label(text, label=label)
                if val:
                    return val, c, label
    # then any chunk that contains the label
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
    """
    Try to extract a pair of numbers (current, prior) for queries like:
      "How did revenue compare to the same quarter last year?"
    Strategy:
      1) Prefer table_row chunks that contain the label_hint (e.g., 'revenue')
         and try to find two numbers on the same line (current, prior).
      2) If not found, scan all chunks containing the label_hint and try again.
      3) If still not found, scan nearby lines for two-number patterns.
    Returns (current_str, prior_str, chunk_or_line_dict) or (None, None, None).
    """
    if not chunks:
        return None, None, None

    # 1) Prefer table rows that include the label
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

    # 2) Any chunk that contains the label
    if label_hint:
        for c in chunks:
            if not c:
                continue
            text = c.get("text", "") or ""
            if label_hint.lower() in text.lower():
                cur, pri, ln = extract_two_period_values_from_row(text, label_hint=label_hint)
                if cur and pri:
                    return cur, pri, c

    # 3) Fallback: try all table_row chunks for any two-number pattern (even without label)
    for c in chunks:
        if not c:
            continue
        ctype = c.get("type", "").lower()
        text = c.get("text", "") or ""
        if ctype.startswith("table"):
            cur, pri, ln = extract_two_period_values_from_row(text, label_hint=None)
            if cur and pri:
                # If label_hint exists, prefer chunks where label is nearby
                if label_hint and label_hint.lower() not in text.lower():
                    # still acceptable as fallback
                    return cur, pri, c
                else:
                    return cur, pri, c

    # 4) Last resort: scan all chunks for any line with two money-like tokens
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
    Returns (description, chunk) or (None, None)
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
