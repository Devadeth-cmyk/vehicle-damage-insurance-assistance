from pathlib import Path
import pymupdf


# --------------------------------------------------
# Folders
# --------------------------------------------------

try:
    from .project_paths import DATA_DIR, PROCESSED_DIR
except ImportError:  # Running directly as `python scripts/extract_text.py`.
    from project_paths import DATA_DIR, PROCESSED_DIR

OUTPUT_DIR = PROCESSED_DIR / "text"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Extract text from one PDF
# --------------------------------------------------

def extract_pdf(pdf_path):
    """
    Extract text from a PDF while preserving
    page boundaries.
    """

    document = pymupdf.open(pdf_path)

    pages = []

    for page_number, page in enumerate(document, start=1):

        text = page.get_text("text")

        page_text = (
            f"\n\n"
            f"===== PAGE {page_number} =====\n\n"
            f"{text.strip()}"
        )

        pages.append(page_text)

    document.close()

    return "\n".join(pages)


# --------------------------------------------------
# Process all PDFs
# --------------------------------------------------

pdf_files = sorted(DATA_DIR.glob("*.pdf"))

print(f"Found {len(pdf_files)} PDF files.")
print()

for pdf_file in pdf_files:

    print(f"Processing: {pdf_file.name}")

    text = extract_pdf(pdf_file)

    output_file = OUTPUT_DIR / f"{pdf_file.stem}.txt"

    output_file.write_text(
        text,
        encoding="utf-8"
    )

    print(f"Saved: {output_file}")
    print()
    

print("Done!")
