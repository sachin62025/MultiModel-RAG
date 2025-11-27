# qa/extractors.py
import re

_money_pat = re.compile(r"(?:\$|\b)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?)\b(?!\s*%)")
_percent_pat = re.compile(r"([0-9]{1,3}(?:\.\d+)?)\s*%")
_two_numbers_line = re.compile(
    r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?)\D+([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?)"
)

_revenue_row = re.compile(r"revenue", re.IGNORECASE)
_repurch_row_keywords = ["repurchase", "repurchased", "share repurchase", "shares repurchased", "buyback", "repurchase of common stock"]


def _clean_text_dedupe(text: str, max_repeat_seq_len: int = 80):
    """
    Remove immediate repeated phrases (OCR or extraction can duplicate headings).
    Simple heuristic: find repeated contiguous substrings and truncate duplicates.
    """
    if not text:
        return text
    # collapse repeated whitespace
    t = re.sub(r'\s+', ' ', text).strip()
    # naive dedupe: if a substring repeats two or more times consecutively, shorten to one
    # check for repeating segments of up to max_repeat_seq_len chars
    for L in range(10, max_repeat_seq_len, 10):
        if len(t) > 2*L:
            sub = t[:L]
            # if the start repeats immediately, cut duplicates
            if t.startswith(sub*2):
                # remove extra repeats
                while t.startswith(sub*2):
                    t = t[len(sub):]
                t = t.strip()
    return t

def extract_first_money_after_label(text: str, label: str):
    """
    Search for the label and return the first non-percentage monetary value found on the same or following lines.
    """
    if not text:
        return None
    txt = text.replace("\r", "\n")
    lines = txt.split("\n")
    label_l = label.lower()
    for i, ln in enumerate(lines):
        if label_l in ln.lower():
            # try to match two numbers on same line
            two = _two_numbers_line.search(ln)
            if two:
                return two.group(1)  # return first (current) by default
            # else find first money not followed by % on same line
            m = _money_pat.search(ln)
            if m:
                return m.group(1)
            # try the next two lines
            for j in range(1, 3):
                if i + j < len(lines):
                    l2 = lines[i + j]
                    if _percent_pat.search(l2):
                        # skip lines that are just percentages
                        continue
                    m2 = _money_pat.search(l2)
                    if m2:
                        return m2.group(1)
    # fallback: search for first money not part of a percent anywhere
    m_any = _money_pat.search(txt)
    if m_any:
        return m_any.group(1)
    return None

def extract_two_period_values_from_row(text: str, label_hint: str = None):
    """
    Attempt to extract two adjacent monetary values for current and prior periods from a single table row or line.
    Returns (value_current, value_prior, chunk_line) or (None, None, None)
    """
    if not text:
        return None, None, None
    txt = text.replace("\r", "\n")
    # look for lines containing the label_hint if provided
    lines = txt.split("\n")
    for ln in lines:
        if label_hint and label_hint.lower() not in ln.lower():
            continue
        # try to find two numbers
        m = _two_numbers_line.search(ln)
        if m:
            return m.group(1), m.group(2), ln
    # fallback: search entire text for a line that contains two numbers close together
    for ln in lines:
        m = _two_numbers_line.search(ln)
        if m:
            return m.group(1), m.group(2), ln
    return None, None, None

def extract_numeric_candidates_from_chunks(chunks: list, labels: list):
    """
    Given list of chunks and labels, return the first found numeric value and the chunk that contained it.
    This prefers exact label matches and avoids percentages.
    """
    for label in labels:
        for c in chunks:
            text = c.get("text","")
            val = extract_first_money_after_label(text, label=label)
            if val:
                return val, c, label
    return None, None, None

def extract_comparison_from_chunks(chunks: list, label: str):
    """
    Try to extract both current and prior values for label (e.g., 'revenue').
    Returns (cur_val, prior_val, chunk_where_found) or (None, None, None)
    """
    # 1) Look for a table row with two numbers on same line
    for c in chunks:
        text = c.get("text","")
        cur, pri, ln = extract_two_period_values_from_row(text, label_hint=label)
        if cur and pri:
            return cur, pri, c
    # 2) If not found, try to get two separate values by searching 'Apr' headings or nearby tokens (less reliable)
    # Try to find the first chunk that includes label and then parse next numbers
    for c in chunks:
        text = c.get("text","")
        if label.lower() in text.lower():
            # find all money matches in chunk (excluding percentages)
            vals = _money_pat.findall(text)
            if len(vals) >= 2:
                return vals[0], vals[1], c
    return None, None, None

def extract_repurchases(chunks: list):
    """
    Search for repurchase-related lines and try to return either monetary or share amounts.
    Returns (description, chunk) or (None, None)
    """
    for c in chunks:
        text = c.get("text","").lower()
        # prefer rows that contain repurchase keywords
        if any(k in text for k in _repurch_row_keywords):
            # try to extract money first
            m = _money_pat.search(text)
            if m:
                return m.group(1), c
            # try to extract shares (e.g., 'X shares repurchased')
            m2 = re.search(r"([0-9]{1,3}(?:,[0-9]{3})*)\s+shares", text)
            if m2:
                return m2.group(1) + " shares", c
            # else return small descriptive snippet
            snippet = text[:400]
            snippet = _clean_text_dedupe(snippet)
            return snippet, c
    return None, None, None

def extract_certification_text(chunks: list):
    """
    Look for chunks mentioning 'certification' or 'exhibit' and return cleaned paragraphs.
    """
    candidates = []
    for c in chunks:
        txt = c.get("text","")
        if 'certificat' in txt.lower() or 'exhibit' in txt.lower() or 'certification' in txt.lower():
            cleaned = _clean_text_dedupe(txt)
            candidates.append((cleaned, c))
    # return the chunk with the longest cleaned text (likely the full certification block)
    if candidates:
        candidates.sort(key=lambda x: len(x[0]), reverse=True)
        return candidates[0]
    return None, None, None



# def extract_first_money_after_label(text: str, label: str):
#     """
#     Search for the label in the text and return the first monetary value found
#     on the same or following lines. Returns a normalized string like '26,044' or None.
#     """
#     if not text:
#         return None
#     txt = text.replace("\r", "\n")
#     lines = txt.split("\n")
#     for i, ln in enumerate(lines):
#         if label.lower() in ln.lower():
#             m = _money_pat.search(ln)
#             if m:
#                 return m.group(1)
#             # try following lines
#             for j in range(1, 3):
#                 if i + j < len(lines):
#                     m2 = _money_pat.search(lines[i + j])
#                     if m2:
#                         return m2.group(1)
#     # fallback: find a revenue-like row anywhere
#     m_row = _revenue_row.search(txt)
#     if m_row:
#         m = _money_pat.search(m_row.group(0))
#         if m:
#             return m.group(1)
#     return None

# def extract_numeric_candidates_from_chunks(chunks: list, labels: list):
#     """
#     Given a list of chunks, returns the first found numeric value and the chunk that contained it.
#     labels: list[str] of labels to try (e.g., ["revenue","cost of revenue"])
#     """
#     for label in labels:
#         for c in chunks:
#             val = extract_first_money_after_label(c.get("text",""), label=label)
#             if val:
#                 return val, c, label
#     # no match
#     return None, None, None
