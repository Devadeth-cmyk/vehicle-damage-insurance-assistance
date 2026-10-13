from pathlib import Path
import pymupdf


# Where our PDF files are located
try:
    from .project_paths import DATA_DIR
except ImportError:  # Running directly as `python scripts/inspect_pdfs.py`.
    from project_paths import DATA_DIR


def inspect_pdf(pdf_path):
    """Inspect one PDF and print basic information."""

    document = pymupdf.open(pdf_path)

    print("=" * 80)
    print(f"FILE: {pdf_path.name}")
    print(f"PAGES: {len(document)}")

    total_characters = 0
    pages_with_text = 0
    pages_without_text = 0

    for page_number, page in enumerate(document, start=1):

        text = page.get_text()

        character_count = len(text)
        total_characters += character_count

        if character_count > 50:
            pages_with_text += 1
        else:
            pages_without_text += 1

        print(
            f"  Page {page_number}: "
            f"{character_count:,} characters"
        )

    print()
    print(f"TOTAL CHARACTERS: {total_characters:,}")
    print(f"PAGES WITH TEXT: {pages_with_text}")
    print(f"PAGES WITH LITTLE/NO TEXT: {pages_without_text}")

    document.close()

    print("=" * 80)
    print()


# Find all PDFs inside the data folder
pdf_files = sorted(DATA_DIR.glob("*.pdf"))

print(f"Found {len(pdf_files)} PDF files.")
print()

if not pdf_files:
    print("ERROR: No PDF files found inside the data folder.")
else:
    for pdf_file in pdf_files:
        inspect_pdf(pdf_file)
