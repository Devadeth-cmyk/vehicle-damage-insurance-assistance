from pathlib import Path
import re


# ============================================================
# Configuration
# ============================================================

try:
    from .project_paths import PROCESSED_DIR
except ImportError:  # Running directly as `python scripts/clean_text.py`.
    from project_paths import PROCESSED_DIR

INPUT_DIR = PROCESSED_DIR / "text"
OUTPUT_DIR = PROCESSED_DIR / "cleaned"


# ============================================================
# Mojibake repair
# ============================================================
#
# These problems usually happen when UTF-8 text is incorrectly
# decoded as Windows-1252/Latin-1.
#
# Examples:
#   â€“   -> –
#   â€”   -> —
#   â€™   -> ’
#   â€œ   -> “
#   â€   -> ”
#   ï¬   -> fi
#
# We repair encoding corruption rather than blindly deleting
# suspicious characters, because insurance documents contain
# important legal terminology and punctuation.
# ============================================================


EXACT_REPLACEMENTS = {
    # UTF-8 punctuation decoded incorrectly
    "â€“": "–",
    "â€”": "—",
    "â€˜": "‘",
    "â€™": "’",
    "â€œ": "“",
    "â€": "”",
    "â€¦": "…",

    # Common quote/dash variants
    "â€": "",
    "â„¢": "™",
    "Â©": "©",
    "Â®": "®",
    "Â°": "°",
    "Â±": "±",

    # Common ligature corruption from PDF extraction
    "ï¬€": "ff",
    "ï¬": "fi",
    "ï¬‚": "fl",
    "ï¬ƒ": "ffi",
    "ï¬„": "ffl",

    # Non-breaking space corruption
    "Â ": " ",

    # Common replacement character
    "\ufffd": " ",
}


# Patterns that strongly indicate mojibake.
#
# These are used for verification, not for indiscriminate deletion.
MOJIBAKE_PATTERNS = [
    r"â[\x80-\xbf]",
    r"Ã[\x80-\xbf]",
    r"Â[\x80-\xbf]",
    r"ï[\x80-\xbf]",
    r"ð[\x80-\xbf]",
    r"â€",
    r"ï¬",
]


def count_mojibake(text: str) -> int:
    """
    Count known mojibake markers in a string.

    This is deliberately conservative. We do not classify every
    non-ASCII character as corruption because legitimate documents
    can contain symbols such as ₹, ©, –, —, etc.
    """
    total = 0

    for pattern in MOJIBAKE_PATTERNS:
        total += len(re.findall(pattern, text))

    return total


def repair_utf8_mojibake(text: str) -> str:
    """
    Repair UTF-8 text that has been incorrectly decoded as
    Windows-1252 / Latin-1.

    The encode/decode approach can repair cases such as:

        â€“ -> –
        â€™ -> ’
        â€œ -> “

    It is attempted only when the text contains strong mojibake
    evidence.

    Multiple passes are allowed because some PDF extraction
    pipelines double-encode text.
    """

    current = text

    for _ in range(3):
        before_count = count_mojibake(current)

        if before_count == 0:
            break

        try:
            repaired = current.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            try:
                repaired = current.encode("cp1252").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                break

        after_count = count_mojibake(repaired)

        # Only accept the automatic encoding repair when it actually
        # improves the text.
        if after_count < before_count:
            current = repaired
        else:
            break

    return current


def apply_exact_replacements(text: str) -> str:
    """
    Apply targeted replacements for known PDF/PDF-extraction
    corruption that may remain after encoding repair.
    """

    for bad, good in EXACT_REPLACEMENTS.items():
        text = text.replace(bad, good)

    return text


def clean_line(line: str) -> str:
    """
    Clean one line without destroying meaningful document content.
    """

    # Remove carriage returns.
    line = line.replace("\r", "")

    # Replace tabs with a normal space.
    line = line.replace("\t", " ")

    # Repair encoding corruption.
    line = repair_utf8_mojibake(line)

    # Apply known safe replacements.
    line = apply_exact_replacements(line)

    # Remove zero-width characters which are normally extraction
    # artifacts and do not carry meaning in these documents.
    line = line.replace("\u200b", "")
    line = line.replace("\u200c", "")
    line = line.replace("\u200d", "")
    line = line.replace("\ufeff", "")

    # Collapse excessive spaces while preserving line structure.
    line = re.sub(r"[ ]{2,}", " ", line)

    return line.rstrip()


def clean_document(text: str) -> str:
    """
    Clean a complete extracted document while preserving page
    boundaries and meaningful text.
    """

    # Normalize line endings first.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # First whole-document repair.
    text = repair_utf8_mojibake(text)

    # Then targeted replacements.
    text = apply_exact_replacements(text)

    # Clean individual lines.
    lines = [clean_line(line) for line in text.split("\n")]

    # Remove excessive blank lines, but preserve page markers.
    cleaned_lines = []

    previous_blank = False

    for line in lines:
        is_blank = not line.strip()

        if is_blank:
            if previous_blank:
                continue

            cleaned_lines.append("")
            previous_blank = True
        else:
            cleaned_lines.append(line)
            previous_blank = False

    return "\n".join(cleaned_lines).strip() + "\n"


def find_remaining_mojibake(text: str):
    """
    Return remaining suspicious strings after cleaning.

    This is a verification step. It does NOT alter the document.
    """

    found = []

    for pattern in MOJIBAKE_PATTERNS:
        matches = re.findall(pattern, text)

        for match in matches:
            if match not in found:
                found.append(match)

    # Also check common explicit corruption sequences.
    for bad in EXACT_REPLACEMENTS:
        if bad and bad in text and bad not in found:
            found.append(bad)

    return found


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_files = sorted(INPUT_DIR.glob("*.txt"))

    if not input_files:
        print(f"No text files found in: {INPUT_DIR.resolve()}")
        return

    print(f"Found {len(input_files)} text files.")
    print()

    total_before = 0
    total_after = 0
    failed_files = []

    for input_file in input_files:
        output_file = OUTPUT_DIR / input_file.name

        # Read explicitly as UTF-8.
        original_text = input_file.read_text(
            encoding="utf-8",
            errors="replace",
        )

        original_length = len(original_text)
        before_mojibake = count_mojibake(original_text)

        cleaned_text = clean_document(original_text)

        after_mojibake = count_mojibake(cleaned_text)

        remaining = find_remaining_mojibake(cleaned_text)

        output_file.write_text(
            cleaned_text,
            encoding="utf-8",
            newline="\n",
        )

        total_before += before_mojibake
        total_after += after_mojibake

        print(
            f"{input_file.name}: "
            f"{original_length:,} → {len(cleaned_text):,} characters"
        )

        print(
            f"  Mojibake markers: "
            f"{before_mojibake} → {after_mojibake}"
        )

        if remaining:
            failed_files.append(input_file.name)

            print(
                "  ⚠ Remaining suspicious sequences:"
                f" {', '.join(repr(x) for x in remaining[:10])}"
            )
        else:
            print("  ✓ Mojibake successfully removed/repaired.")

        print()

    print("=" * 80)
    print()

    if failed_files:
        print("⚠ CLEANING COMPLETED WITH WARNINGS")
        print()
        print("Files requiring manual review:")

        for filename in failed_files:
            print(f"  - {filename}")

        print()
        print(
            "Do NOT proceed to chunking until the remaining "
            "sequences have been reviewed."
        )
    else:
        print("✓ CLEANING SUCCESSFUL")
        print("✓ No known mojibake remains in the cleaned files.")

    print()
    print(f"Total mojibake markers before: {total_before}")
    print(f"Total mojibake markers after:  {total_after}")
    print()
    print("Output directory:")
    print(OUTPUT_DIR.resolve())


if __name__ == "__main__":
    main()
