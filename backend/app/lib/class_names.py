import re

FORMAT_HELP = (
    "Use a grade and one letter, such as 8A, or a grade and a section name, such as 8 Name1."
)

_LETTER = re.compile(r"^(\d{1,2})([A-Za-z])$")
_NAMED = re.compile(r"^(\d{1,2}) ([A-Za-z][A-Za-z0-9]*)$")
_STORED_LETTER = re.compile(r"^(\d{1,2})\s*-?\s*([A-Za-z])$")
_STORED_NAMED = re.compile(r"^(\d{1,2})\s+([A-Za-z][A-Za-z0-9]*)$")


def class_identity(name: str) -> str:
    trimmed = re.sub(r"^class\s+", "", name.strip(), flags=re.IGNORECASE)
    letter = _STORED_LETTER.match(trimmed)
    if letter:
        grade = int(letter.group(1))
        if 1 <= grade <= 12:
            return f"{grade}:{letter.group(2).upper()}"
    named = _STORED_NAMED.match(trimmed)
    if named:
        grade = int(named.group(1))
        if 1 <= grade <= 12:
            return f"{grade}:{named.group(2).lower()}"
    return trimmed.lower()


def parse_class_name(raw: str) -> tuple[int, str, str, str]:
    text = re.sub(r"\s+", " ", raw.strip())
    if not text:
        raise ValueError("Enter a class name.")

    letter = _LETTER.match(text)
    if letter:
        grade = int(letter.group(1))
        if grade < 1 or grade > 12:
            raise ValueError("Grade must be from 1 to 12.")
        section = letter.group(2).upper()
        display = f"{grade}{section}"
        return grade, section, display, f"{grade}:{section}"

    named = _NAMED.match(text)
    if named:
        grade = int(named.group(1))
        if grade < 1 or grade > 12:
            raise ValueError("Grade must be from 1 to 12.")
        section = named.group(2)
        display = f"{grade} {section}"
        return grade, section, display, f"{grade}:{section.lower()}"

    raise ValueError(f"That name is not a supported class format. {FORMAT_HELP}")
