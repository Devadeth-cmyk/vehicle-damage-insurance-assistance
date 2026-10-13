import json
import re
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

try:
    from .project_paths import PROJECT_ROOT as BASE_DIR
except ImportError:  # Running directly as `python scripts/chunk_text.py`.
    from project_paths import PROJECT_ROOT as BASE_DIR

INPUT_DIR = BASE_DIR / "processed" / "cleaned"
OUTPUT_DIR = BASE_DIR / "processed" / "chunks"

CHUNK_SIZE = 160
CHUNK_OVERLAP = 40

# Recognized standalone policy headings. These are used as section boundaries;
# numbered clauses remain together with their surrounding section.
SECTION_HEADING_RE = re.compile(
    r"^(?:"
    r"GENERAL\s+EXCEPTIONS(?:\s*\([^\n]*\))?"
    r"|DEDUCTIBLE"
    r"|CONDITIONS"
    r"|DEFINITIONS"
    r"|LIMITATIONS\s+AS\s+TO\s+USE"
    r"|SECTION\s+(?:I{1,3}|IV|V|VI|[1-6])\b.*"
    r"|LIABILITY\s+TO\s+THIRD\s+PARTIES"
    r"|LOSS\s+OF\s+OR\s+DAMAGE\s+TO\s+THE\s+VEHICLE(?:\s+INSURED)?"
    r")\s*$",
    re.IGNORECASE,
)

# ============================================================
# MOJIBAKE / ENCODING VALIDATION
# ============================================================

MOJIBAKE_MARKERS = [
    "\u00e2",  # Common marker for incorrectly decoded UTF-8 punctuation
    "\u00ef",  # Common marker for incorrectly decoded UTF-8 punctuation
    "\ufffd",  # Unicode replacement character
]


def check_for_mojibake(text):
    """Return obvious mojibake markers found in text."""
    return [marker for marker in MOJIBAKE_MARKERS if marker in text]


def validate_unicode(text, filename):
    """Validate text and report whether common Unicode punctuation survives."""
    bad_markers = check_for_mojibake(text)
    if bad_markers:
        print(f"  WARNING: Possible mojibake found in {filename}: {bad_markers}")
        return False

    unicode_chars = {
        "en dash": "\u2013",
        "em dash": "\u2014",
        "left quote": "\u201c",
        "right quote": "\u201d",
        "apostrophe": "\u2019",
    }
    found_unicode = [name for name, char in unicode_chars.items() if char in text]

    if found_unicode:
        print("  Unicode punctuation preserved: " + ", ".join(found_unicode))
    else:
        print("  No suspicious mojibake detected.")
    return True


# ============================================================
# COMPANY NAME
# ============================================================


def clean_company_name(filename):
    """Map source filenames to canonical company names."""
    name = Path(filename).stem
    replacements = {
        "Acko Car Package Policy": "Acko General Insurance",
        "Bajaj Allianz General Insurance Company": "Bajaj Allianz General Insurance",
        "car-Policy-wording": "Bajaj Allianz General Insurance",
        "Cholamandalam MS General Insurance Company Limited": "Cholamandalam MS General Insurance",
        "Digit Private Car Policy": "Digit Insurance",
        "HDFC ERGO Comprehensive": "HDFC ERGO",
        "ICICI Lombard General Insurance Company Limited": "ICICI Lombard General Insurance",
        "IndusInd General Insurance Company Limited": "IndusInd General Insurance",
        "SBI General Insurance Company Limited": "SBI General Insurance",
        "Shriram General Insurance Co. Ltd": "Shriram General Insurance",
        "TATA AIG General Insurance": "TATA AIG General Insurance",
    }
    return replacements.get(name, name)


# ============================================================
# PAGE EXTRACTION / TEXT NORMALIZATION
# ============================================================


def extract_pages(text):
    """Split cleaned document text using the PAGE markers produced by extraction."""
    pattern = r"===== PAGE (\d+) ====="
    matches = list(re.finditer(pattern, text))
    pages = []

    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            pages.append({"page_number": int(match.group(1)), "content": content})
    return pages


def normalize_text(text):
    """Normalize whitespace without removing Unicode punctuation."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\.{3,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_words(text):
    return text.split()


# ============================================================
# SECTION-AWARE CHUNK CREATION
# ============================================================


def split_pages_into_sections(pages):
    """Split at recognized headings and retain the page number for each word."""
    sections = []
    current_heading = "Document text"
    current_words = []

    def flush():
        nonlocal current_words
        if current_words:
            sections.append({"heading": current_heading, "words_with_pages": current_words})
            current_words = []

    for page in pages:
        page_number = page["page_number"]
        content = normalize_text(page["content"])

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue

            # A heading is treated as a boundary only when it occupies its own line.
            # This avoids splitting ordinary prose that merely mentions a heading.
            if SECTION_HEADING_RE.fullmatch(line):
                flush()
                current_heading = line

            for word in split_into_words(line):
                current_words.append({"word": word, "page": page_number})

    flush()
    return sections


def create_chunks(pages, document_name, company_name):
    """Create overlapping chunks inside policy sections while preserving page metadata."""
    sections = split_pages_into_sections(pages)
    chunks = []
    chunk_number = 1

    for section in sections:
        words_with_pages = section["words_with_pages"]
        total_words = len(words_with_pages)
        start = 0

        while start < total_words:
            end = min(start + CHUNK_SIZE, total_words)
            selected = words_with_pages[start:end]
            if not selected:
                break

            chunk_words = [item["word"] for item in selected]
            page_numbers = sorted({item["page"] for item in selected})
            chunk_content = " ".join(chunk_words).strip()

            bad_markers = check_for_mojibake(chunk_content)
            if bad_markers:
                raise ValueError(
                    f"Mojibake detected in {document_name}, chunk {chunk_number}: {bad_markers}"
                )

            safe_stem = Path(document_name).stem.lower().replace(" ", "_")
            chunk_id = f"{safe_stem}_chunk_{chunk_number:04d}"

            chunks.append({
                "chunk_id": chunk_id,
                "document": document_name,
                "company": company_name,
                "page_start": page_numbers[0],
                "page_end": page_numbers[-1],
                "pages": page_numbers,
                "chunk_number": chunk_number,
                "word_count": len(chunk_words),
                "section": section["heading"],
                "content": chunk_content,
            })

            chunk_number += 1
            if end >= total_words:
                break
            start = end - CHUNK_OVERLAP

    return chunks


# ============================================================
# JSON VALIDATION / SAVING
# ============================================================


def validate_chunks(chunks, document_name):
    """Validate generated chunks before and after JSON serialization."""
    for chunk in chunks:
        content = chunk.get("content", "")
        if "\ufffd" in content:
            raise ValueError(
                f"Replacement character found in {document_name}, chunk {chunk['chunk_number']}"
            )
        for marker in ["\u00e2", "\u00ef"]:
            if marker in content:
                raise ValueError(
                    f"Mojibake character {repr(marker)} found in {document_name}, "
                    f"chunk {chunk['chunk_number']}"
                )
    return True


def save_json(output_file, data):
    """Save JSON as UTF-8 while preserving Unicode characters."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")


# ============================================================
# MAIN
# ============================================================


def main():
    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    text_files = sorted(INPUT_DIR.glob("*.txt"))
    if not text_files:
        print(f"No .txt files found in: {INPUT_DIR}")
        return

    print(f"Found {len(text_files)} cleaned text files.\n")
    all_chunks = []
    processed_documents = 0

    for text_file in text_files:
        print("=" * 80)
        print(f"Processing: {text_file.name}")
        text = text_file.read_text(encoding="utf-8")
        print(f"Characters read: {len(text):,}")

        if not validate_unicode(text, text_file.name):
            raise ValueError(f"Input text failed Unicode validation: {text_file.name}")

        pages = extract_pages(text)
        if not pages:
            print("WARNING: No page markers found; skipping document.")
            continue

        document_name = text_file.stem
        company_name = clean_company_name(text_file.name)
        chunks = create_chunks(pages, document_name, company_name)
        validate_chunks(chunks, document_name)

        output_file = OUTPUT_DIR / f"{document_name}.json"
        save_json(output_file, chunks)

        verification_data = json.loads(output_file.read_text(encoding="utf-8"))
        validate_chunks(verification_data, document_name)
        if verification_data != chunks:
            raise ValueError(f"JSON verification mismatch: {output_file}")

        all_chunks.extend(verification_data)
        processed_documents += 1
        print(f"Pages: {len(pages)}")
        print(f"Chunks: {len(chunks)}")
        print(f"Output: {output_file}")
        print("JSON UTF-8 verification passed.\n")

    combined_file = OUTPUT_DIR / "all_chunks.json"
    save_json(combined_file, all_chunks)
    combined_data = json.loads(combined_file.read_text(encoding="utf-8"))
    validate_chunks(combined_data, "all_chunks.json")

    if len(combined_data) != len(all_chunks):
        raise ValueError("Combined JSON chunk-count validation failed.")

    print("\n" + "=" * 80)
    print("CHUNKING COMPLETE")
    print("=" * 80)
    print(f"Documents processed: {processed_documents}")
    print(f"Total chunks: {len(all_chunks)}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Combined file: {combined_file}")
    print("Unicode, chunk, and JSON validation passed.")

    for chunk in all_chunks:
        content = chunk.get("content", "")
        if "\u2013" in content:
            index = content.find("\u2013")
            print("Unicode verification example:")
            print(repr(content[max(0, index - 20):index + 30]))
            print("Unicode code point:", hex(ord(content[index])))
            break

    print("RESULT: PASS")


if __name__ == "__main__":
    main()
