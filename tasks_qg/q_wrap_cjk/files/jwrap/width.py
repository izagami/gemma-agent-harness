"""Display width of characters in a terminal."""
import unicodedata


def char_width(ch):
    """Columns one character takes."""
    return 2 if unicodedata.east_asian_width(ch) == "W" else 1


def text_width(s):
    return sum(char_width(c) for c in s)
