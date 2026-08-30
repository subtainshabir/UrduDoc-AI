import re

ZERO_WIDTH_CHARS = ["\ufeff", "\u200b", "\u200c", "\u200d"]

REPEATED_SPACE_PATTERN = re.compile(r"[ \t]+")

UNCERTAIN_MARKER_PATTERN = re.compile(r"\[unclear\]", re.IGNORECASE)


def clean_text(text: str) -> str:
    if not text:
        return text

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    for char in ZERO_WIDTH_CHARS:
        normalized = normalized.replace(char, "")

    lines = normalized.split("\n")
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        line = REPEATED_SPACE_PATTERN.sub(" ", line)
        cleaned_lines.append(line)

    final_lines = []
    blank_streak = 0

    for line in cleaned_lines:
        if line == "":
            blank_streak += 1
            if blank_streak > 1:
                continue
        else:
            blank_streak = 0
        final_lines.append(line)

    while final_lines and final_lines[0] == "":
        final_lines.pop(0)

    while final_lines and final_lines[-1] == "":
        final_lines.pop()

    return "\n".join(final_lines)


def count_uncertain_markers(text: str) -> int:
    if not text:
        return 0
    return len(UNCERTAIN_MARKER_PATTERN.findall(text))


def has_uncertain_text(text: str) -> bool:
    return count_uncertain_markers(text) > 0