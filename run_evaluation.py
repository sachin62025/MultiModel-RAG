# evaluation/run_evaluation.py
"""
Evaluation Script for Multi-Modal RAG QA System
Computes:
 - Precision@K
 - Recall@K
 - Numeric Extraction Accuracy
 - Overall QA Accuracy (optional)
"""

import json
from typing import List, Dict
from qa.generator import answer_query


# ---------------------------------------------
# 1. Define your evaluation set
# ---------------------------------------------
# Format:
# {
#   "question": "...",
#   "answer": "<expected numeric or text>",
#   "page": <expected page number - optional>,
#   "keywords": ["word1","word2"]  # used for retrieval metrics
# }

EVAL_DATA: List[Dict] = [
    {
        "question": "What was NVIDIA’s total revenue for the reported quarter?",
        "answer": "26044",
        "keywords": ["revenue", "26044"]
    },
    {
        "question": "How did revenue compare to the same quarter last year?",
        "answer": "26044|7192",
        "keywords": ["revenue"]
    },
    {
        "question": "What was the net income for this quarter?",
        "answer": "14881",
        "keywords": ["income"]
    },
    {
        "question": "What were cash and cash equivalents?",
        "answer": "7587",
        "keywords": ["cash"]
    }
]

# ---------------------------------------------
# Helper: normalize numeric values
# ---------------------------------------------
import re

def extract_number(text: str):
    if not text:
        return None
    nums = re.findall(r"[0-9][0-9,]*\.?[0-9]*", text)
    if not nums:
        return None
    return nums[0].replace(",", "")

# ---------------------------------------------
# Evaluate Retrieval (Precision@K / Recall@K)
# ---------------------------------------------
def evaluate_retrieval(retrieved_chunks, keywords, k=5):
    """
    retrieved_chunks = answer["retrieved"] from answer_query()
    keywords = list of ground-truth terms
    """
    retrieved_texts = [c["text"].lower() for c in retrieved_chunks[:k]]

    gt_hits = 0
    for kw in keywords:
        if any(kw.lower() in t for t in retrieved_texts):
            gt_hits += 1

    total_keywords = len(keywords)
    precision = gt_hits / k
    recall = gt_hits / total_keywords if total_keywords > 0 else 0

    return precision, recall


# ---------------------------------------------
# Main Evaluation
# ---------------------------------------------
def run_evaluation(top_k=8):
    total = len(EVAL_DATA)
    numeric_correct = 0
    retrieval_precision_scores = []
    retrieval_recall_scores = []

    print("\n===== Running Evaluation =====")

    for item in EVAL_DATA:
        q = item["question"]
        expected = item["answer"]
        keywords = item["keywords"]

        print(f"\nQ: {q}")

        result = answer_query(q, top_k=top_k)

        # ----- Numeric Accuracy -----
        predicted = extract_number(result["answer"])
        expected_primary = expected.split("|")[0]

        numeric_ok = (predicted == expected_primary)
        if numeric_ok:
            numeric_correct += 1

        # ----- Retrieval Metrics -----
        Pk, Rk = evaluate_retrieval(result["retrieved"], keywords, k=5)
        retrieval_precision_scores.append(Pk)
        retrieval_recall_scores.append(Rk)

        print(f"Predicted: {predicted}, Expected: {expected_primary}, Numeric Correct? {numeric_ok}")
        print(f"Precision@5: {Pk:.2f}, Recall@5: {Rk:.2f}")

    # Summary
    print("\n========== FINAL RESULTS ==========")
    print(f"Numeric Extraction Accuracy: {numeric_correct}/{total} = {numeric_correct/total:.2f}")
    print(f"Mean Precision@5: {sum(retrieval_precision_scores)/total:.2f}")
    print(f"Mean Recall@5: {sum(retrieval_recall_scores)/total:.2f}")


if __name__ == "__main__":
    run_evaluation()
