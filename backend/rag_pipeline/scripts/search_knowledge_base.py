"""Semantic search over the ChromaDB policy index.

This is an importable module (no code runs at import time). The embedding model
and the Chroma collection are loaded lazily on the first search and reused.

    from search_knowledge_base import search_knowledge_base, get_companies
    hits = search_knowledge_base("Is engine damage covered?", company="ICICI Lombard")

Run `python search_knowledge_base.py "your question" [--company NAME]` for a quick test.
"""

import argparse
import threading

try:
    from . import rag_config as cfg
except ImportError:
    import rag_config as cfg


class KnowledgeBaseNotReady(RuntimeError):
    """The vector database has not been built yet."""


class UnknownCompany(ValueError):
    """The requested insurer does not exist in the index."""


_lock = threading.Lock()
_state = {}


def _norm(text):
    return " ".join(str(text).split())


def _init():
    """Load model + collection once (thread-safe)."""
    if _state:
        return _state
    with _lock:
        if _state:
            return _state

        import chromadb
        from sentence_transformers import SentenceTransformer

        client = chromadb.PersistentClient(path=str(cfg.VECTOR_DB_DIR))
        try:
            collection = client.get_collection(cfg.COLLECTION_NAME)
        except Exception as exc:
            raise KnowledgeBaseNotReady(
                f"Vector collection '{cfg.COLLECTION_NAME}' not found in {cfg.VECTOR_DB_DIR}. "
                "Run: python scripts/chunk_text.py && python scripts/build_vector_db.py"
            ) from exc

        meta = collection.metadata or {}
        # Always embed queries with the same model that built the index.
        model_name = meta.get("embedding_model", cfg.EMBEDDING_MODEL)
        model = SentenceTransformer(model_name)

        all_meta = collection.get(include=["metadatas"])["metadatas"] or []
        company_map = {}
        for m in all_meta:
            name = _norm(m.get("company", ""))
            if not name:
                continue
            if any(marker in name for marker in cfg.EXCLUDED_COMPANY_MARKERS):
                continue
            company_map[name.lower()] = name

        _state.update(
            model=model,
            collection=collection,
            company_map=company_map,
            companies=sorted(company_map.values()),
        )
        return _state


def get_companies():
    """Sorted list of selectable insurers."""
    return list(_init()["companies"])


def resolve_company(company):
    """Return the canonical company name (case/space-insensitive) or raise UnknownCompany."""
    canon = _init()["company_map"].get(_norm(company).lower())
    if canon is None:
        raise UnknownCompany(f"Unknown insurance company: {company!r}")
    return canon


def search_knowledge_base(question, company=None, top_k=None, min_similarity=None):
    """Return up to top_k chunks ranked by cosine similarity (highest first).

    Each result: chunk_id, company, document, page_start, page_end, content, similarity.
    """
    question = (question or "").strip()
    if not question:
        return []

    top_k = top_k or cfg.TOP_K
    min_similarity = cfg.SIMILARITY_THRESHOLD if min_similarity is None else min_similarity

    state = _init()

    
    # Direct retrieval for broad general-exclusion questions.
    question_lower = question.lower()
    exclusion_terms = (
        "general exclusion",
        "general exception",
        "general exclusions",
        "general exceptions",
    )

    if any(term in question_lower for term in exclusion_terms):
        company_name = resolve_company(company) if company else None

        where_conditions = [
            {"section": "GENERAL EXCEPTIONS"}
        ]
        if company_name:
            where_conditions.append({"company": company_name})

        where = (
            where_conditions[0]
            if len(where_conditions) == 1
            else {"$and": where_conditions}
        )

        data = state["collection"].get(
            where=where,
            include=["documents", "metadatas"],
        )

        results = []
        for chunk_id, doc, meta in zip(
            data["ids"], data["documents"], data["metadatas"]
        ):
            results.append({
                "chunk_id": chunk_id,
                "company": meta.get("company", ""),
                "document": meta.get("document", "Unknown"),
                "page_start": meta.get("page_start", 0),
                "page_end": meta.get("page_end", 0),
                "content": doc,
                "similarity": None,
                "chunk_number": meta.get("chunk_number", 0),
            })

        results.sort(key=lambda r: r["chunk_number"])
        return results

    where = {"company": resolve_company(company)} if company else None

    count = state["collection"].count()
    if count == 0:
        return []

    query_vec = state["model"].encode(question, normalize_embeddings=True).tolist()
    res = state["collection"].query(
        query_embeddings=[query_vec],
        n_results=min(top_k, count),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    results = []
    for chunk_id, doc, meta, dist in zip(
        res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        similarity = 1.0 - float(dist)  # collection uses cosine distance

        results.append(
            {
                "chunk_id": chunk_id,
                "company": meta.get("company", ""),
                "document": meta.get("document", "Unknown"),
                "page_start": meta.get("page_start", 0),
                "page_end": meta.get("page_end", 0),
                "content": doc,
                "similarity": similarity,
            }
        )
    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search the insurance knowledge base")
    parser.add_argument("question")
    parser.add_argument("--company", default=None)
    parser.add_argument("--top-k", type=int, default=cfg.TOP_K)
    args = parser.parse_args()

    
    for i, hit in enumerate(
        search_knowledge_base(args.question, args.company, args.top_k), 1
    ):
        sim_text = (
            f"{hit['similarity']:.3f}"
            if hit["similarity"] is not None
            else "section match"
        )

        print(
            f"{i}. {hit['company']} | {hit['document']} | "
            f"pp.{hit['page_start']}-{hit['page_end']} | sim={sim_text}"
        )
        print(f"   {hit['content'][:200]}...\n")
