"""Retrieval evaluation using the real search module (same code path as the app).

A question passes only if at least one retrieved chunk contains one of its
expected keywords - not merely if *something* was retrieved (the old check).

    python scripts/evaluate_retrieval.py            # all insurers pooled
    python scripts/evaluate_retrieval.py --per-company
"""

import argparse

try:
    from . import rag_config as cfg
    from .search_knowledge_base import get_companies, search_knowledge_base
except ImportError:
    import rag_config as cfg
    from search_knowledge_base import get_companies, search_knowledge_base

# (question, keywords - any one appearing in a top-k chunk counts as a hit)
TESTS = [
    ("What is covered under own damage?", ["own damage", "own-damage"]),
    ("What is the personal accident cover for owner driver?", ["personal accident", "owner-driver", "owner driver"]),
    ("What are the general exclusions?", ["exclusion", "not covered", "shall not be liable"]),
    ("What is zero depreciation?", ["zero depreciation", "nil depreciation", "depreciation"]),
    ("What is roadside assistance?", ["roadside", "road side", "towing"]),
    ("What is the claim procedure?", ["claim", "intimat"]),
    ("What documents are required for a claim?", ["document", "claim form", "driving licen"]),
    ("Is engine damage covered?", ["engine"]),
    ("What is the voluntary deductible?", ["deductible", "excess"]),
    ("What happens in case of total loss?", ["total loss", "constructive total loss", "idv"]),
]

PASS_RATE = 0.7


def run(company=None):
    hits = 0
    for question, keywords in TESTS:
        results = search_knowledge_base(question, company=company, top_k=cfg.TOP_K)
        text = " ".join(r["content"].lower() for r in results)
        ok = any(k in text for k in keywords)
        hits += ok
        # Direct section lookups (for example, GENERAL EXCEPTIONS) return
        # similarity=None because they use metadata filtering, not vector
        # ranking. Keep that valid result from crashing the benchmark output.
        similarity = results[0].get("similarity") if results else None
        best = f"{similarity:.3f}" if isinstance(similarity, (int, float)) else (
            "section match" if results else "-"
        )
        print(f"  {'PASS' if ok else 'FAIL'}  best_sim={best}  {question}")
    return hits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-company", action="store_true")
    args = parser.parse_args()

    scopes = get_companies() if args.per_company else [None]
    total_hits = total = 0
    for company in scopes:
        print(f"\n=== {company or 'ALL COMPANIES'} ===")
        total_hits += run(company)
        total += len(TESTS)

    rate = total_hits / total if total else 0
    print(f"\nHit rate: {total_hits}/{total} ({rate:.0%})")
    print("RESULT: PASS" if rate >= PASS_RATE else "RESULT: CHECK REQUIRED")


if __name__ == "__main__":
    main()
