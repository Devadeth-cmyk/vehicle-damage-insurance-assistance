"""Build the ChromaDB index from processed/chunks/all_chunks.json.

Differences from the old version:
  * cosine distance space (so similarity = 1 - distance is correct)
  * normalized embeddings
  * company names whitespace-normalized so company filters match exactly
  * reports how many chunks exceed the embedding model's token limit
"""

import json

import chromadb
from sentence_transformers import SentenceTransformer

try:
    from . import rag_config as cfg
except ImportError:
    import rag_config as cfg

BATCH_SIZE = 64
ADD_BATCH = 500


def load_chunks():
    if not cfg.CHUNKS_FILE.exists():
        raise FileNotFoundError(f"Chunks file not found: {cfg.CHUNKS_FILE}")
    with cfg.CHUNKS_FILE.open("r", encoding="utf-8") as f:
        chunks = json.load(f)
    if not chunks:
        raise ValueError("No chunks found in all_chunks.json")
    return chunks


def prepare(chunks):
    ids, docs, metas, seen = [], [], [], set()
    skipped = 0
    for chunk in chunks:
        content = str(chunk.get("content") or chunk.get("text") or "").strip()
        chunk_id = str(chunk.get("chunk_id", "")).strip()
        if not content or not chunk_id or chunk_id in seen:
            skipped += 1
            continue
        seen.add(chunk_id)
        ids.append(chunk_id)
        docs.append(content)
        
        metas.append(
            {
                "document": str(chunk.get("document", "")),
                "company": " ".join(str(chunk.get("company", "")).split()),
                "page_start": int(chunk.get("page_start", 0) or 0),
                "page_end": int(chunk.get("page_end", 0) or 0),
                "chunk_number": int(chunk.get("chunk_number", 0) or 0),
                "word_count": int(chunk.get("word_count", 0) or 0),
                "section": str(chunk.get("section", "") or ""),
            }
        )

    return ids, docs, metas, skipped


def report_truncation(model, docs):
    """Chunks longer than the model's max sequence length are silently truncated
    by sentence-transformers, which hurts retrieval. Surface that."""
    limit = model.max_seq_length
    backend_tokenizer = getattr(model.tokenizer, "backend_tokenizer", None)
    if backend_tokenizer is not None:
        lengths = [
            len(backend_tokenizer.encode(d, add_special_tokens=True).ids)
            for d in docs
        ]
    else:
        lengths = [
            len(model.tokenizer(d, add_special_tokens=True)["input_ids"])
            for d in docs
        ]
    over = sum(1 for n in lengths if n > limit)
    print(f"Embedding limit: {limit} tokens | longest chunk: {max(lengths)} tokens")
    if over:
        pct = 100 * over / len(docs)
        print(
            f"ERROR: {over}/{len(docs)} chunks ({pct:.0f}%) exceed the model limit."
        )
        raise ValueError("Refusing to embed chunks that would be silently truncated.")
    else:
        print("✓ No chunk exceeds the embedding token limit.")


def split_oversized_chunks(ids, docs, metas, model):
    """Split pathological PDF/OCR chunks to avoid silent model truncation."""
    tokenizer = model.tokenizer
    # Leave room for special tokens and for minor tokenizer decode/re-encode
    # differences so the persisted text stays below the model's hard limit.
    max_content_tokens = max(1, model.max_seq_length - 32)
    split_ids, split_docs, split_metas = [], [], []
    split_count = 0
    backend_tokenizer = getattr(tokenizer, "backend_tokenizer", None)

    for chunk_id, document, metadata in zip(ids, docs, metas):
        if backend_tokenizer is not None:
            token_ids = backend_tokenizer.encode(
                document, add_special_tokens=False
            ).ids
        else:
            token_ids = tokenizer.encode(document, add_special_tokens=False)
        pieces = [
            token_ids[start:start + max_content_tokens]
            for start in range(0, len(token_ids), max_content_tokens)
        ] or [[]]

        if len(pieces) == 1:
            split_ids.append(chunk_id)
            split_docs.append(document)
            split_metas.append(metadata)
            continue

        split_count += 1
        for part_number, piece in enumerate(pieces, start=1):
            split_ids.append(f"{chunk_id}_part_{part_number}")
            split_docs.append(tokenizer.decode(piece, skip_special_tokens=True))
            split_metas.append({
                **metadata,
                "source_chunk_id": chunk_id,
                "token_part": part_number,
                "token_parts": len(pieces),
            })

    print(f"Split {split_count} oversized source chunks into {len(split_ids)} index chunks.")
    return split_ids, split_docs, split_metas


def main():
    print("=" * 80)
    print("INSURANCE KNOWLEDGE BASE - VECTOR DATABASE BUILDER")
    print("=" * 80)

    chunks = load_chunks()
    ids, docs, metas, skipped = prepare(chunks)
    print(f"✓ Loaded {len(chunks)} chunks ({len(ids)} usable, {skipped} skipped)")
    if not ids:
        raise SystemExit("Nothing to index.")

    print(f"\nLoading embedding model: {cfg.EMBEDDING_MODEL}")
    model = SentenceTransformer(cfg.EMBEDDING_MODEL)
    ids, docs, metas = split_oversized_chunks(ids, docs, metas, model)
    report_truncation(model, docs)

    cfg.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(cfg.VECTOR_DB_DIR))
    try:
        client.delete_collection(cfg.COLLECTION_NAME)
        print("✓ Existing collection removed")
    except Exception:
        pass

    collection = client.create_collection(
        name=cfg.COLLECTION_NAME,
        metadata={
            "description": "Insurance policy knowledge base",
            "embedding_model": cfg.EMBEDDING_MODEL,
            "hnsw:space": "cosine",
        },
    )

    print(f"\nEmbedding {len(docs)} chunks...")
    embeddings = model.encode(
        docs,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    for i in range(0, len(ids), ADD_BATCH):
        sl = slice(i, i + ADD_BATCH)
        collection.add(
            ids=ids[sl],
            documents=docs[sl],
            metadatas=metas[sl],
            embeddings=embeddings[sl].tolist(),
        )

    count = collection.count()
    if count != len(ids):
        raise RuntimeError(f"Vector count mismatch: expected {len(ids)}, got {count}")

    companies = sorted({m["company"] for m in metas if m["company"]})
    print("\n" + "=" * 80)
    print("BUILD COMPLETE")
    print("=" * 80)
    print(f"Vectors   : {count}")
    print(f"Companies : {len(companies)}")
    print(f"Database  : {cfg.VECTOR_DB_DIR}")
    print("RESULT: PASS")


if __name__ == "__main__":
    main()
