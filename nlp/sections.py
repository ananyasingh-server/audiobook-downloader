import re


def detect_sections(text):
    """
    Detects chapters/sections in Project Gutenberg books.

    Gutenberg books often contain a Table of Contents before
    the actual book. Therefore, if the same chapter appears
    multiple times, we use the LAST occurrence as the real
    chapter.

    Example:

        CONTENTS
        Chapter 1
        Chapter 2

        Chapter 1
        Actual chapter content...

        Chapter 2
        Actual chapter content...
    """

    if not text or not text.strip():
        return [
            {
                "title": "Full Book",
                "text": ""
            }
        ]

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # ---------------------------------------------------------
    # Detect chapter headings
    # ---------------------------------------------------------
    #
    # Supports:
    #
    # Chapter 1
    # Chapter 2
    # CHAPTER I
    # CHAPTER II
    # CHAPTER V. Letters—Lucy and Mina
    # Chapter 1.
    #
    # Also supports Gutenberg's occasional:
    #
    # C HAPTER I.
    #
    # The heading must be on its own line.
    # ---------------------------------------------------------

    chapter_pattern = re.compile(
        r"^\s*"
        r"(C\s*HAPTER|Chapter|CHAPTER)"
        r"\s+"
        r"("
        r"[IVXLCDM]+"
        r"|"
        r"\d+"
        r")"
        r"(?:[.:]?\s*[^\n]*)?"
        r"\s*$",
        re.MULTILINE
    )

    matches = list(chapter_pattern.finditer(text))

    # ---------------------------------------------------------
    # No chapters detected
    # ---------------------------------------------------------

    if not matches:
        return [
            {
                "title": "Full Book",
                "text": text.strip()
            }
        ]

    # ---------------------------------------------------------
    # Keep only the LAST occurrence of each chapter number
    # ---------------------------------------------------------
    #
    # This removes Table-of-Contents entries.
    # ---------------------------------------------------------

    last_occurrence = {}

    for match in matches:

        chapter_number = match.group(2).upper()

        last_occurrence[chapter_number] = match

    # Sort the actual chapter matches according to their
    # position in the book.

    actual_matches = sorted(
        last_occurrence.values(),
        key=lambda match: match.start()
    )

    sections = []

    # ---------------------------------------------------------
    # Build sections
    # ---------------------------------------------------------

    for index, match in enumerate(actual_matches):

        chapter_number = match.group(2).upper()

        # Clean chapter title
        title = f"CHAPTER {chapter_number}"

        start = match.start()

        if index + 1 < len(actual_matches):

            end = actual_matches[index + 1].start()

        else:

            end = len(text)

        section_text = text[start:end].strip()

        if not section_text:
            continue

        sections.append(
            {
                "title": title,
                "text": section_text
            }
        )

    # ---------------------------------------------------------
    # Safety fallback
    # ---------------------------------------------------------

    if not sections:

        return [
            {
                "title": "Full Book",
                "text": text.strip()
            }
        ]

    return sections