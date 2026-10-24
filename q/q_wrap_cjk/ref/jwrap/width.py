"""Display width of characters in a terminal."""
import unicodedata


def char_width(ch):
    """Columns one character takes."""
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def text_width(s):
    return sum(char_width(c) for c in s)
