"""Normalization helpers.

*_key() functions build comparison keys (never stored); clean_*() functions produce
the values that are stored and shown to users.
"""
import re
import unicodedata

_SPACES = re.compile(r"\s+")


def clean_name(s):
    """Display form of a person's name: trimmed, inner whitespace collapsed to one space."""
    return _SPACES.sub(" ", s.replace("　", " ")).strip()


def clean_email(s):
    return s.strip()


def clean_phone(s):
    """Keep the vendor's formatting but normalise full-width digits and hyphens."""
    s = unicodedata.normalize("NFKC", s).strip()
    return s.replace("ー", "-").replace("−", "-")


def name_key(s):
    """Names compare equal regardless of width, case and whitespace."""
    s = unicodedata.normalize("NFKC", s)
    return _SPACES.sub("", s).casefold()


def email_key(s):
    s = unicodedata.normalize("NFKC", s).strip()
    return s.casefold()


def phone_key(s):
    """Digits only; a leading +81 country code becomes 0."""
    digits = re.sub(r"\D", "", unicodedata.normalize("NFKC", s))
    if digits.startswith("81") and s.strip().startswith("+"):
        digits = "0" + digits[2:]
    return digits
