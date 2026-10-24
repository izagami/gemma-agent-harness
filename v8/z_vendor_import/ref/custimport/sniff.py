"""Character-encoding detection for vendor files.

Vendors send either UTF-8 (some tools add a BOM) or Shift_JIS (Windows code page 932).
Decoding a multi-megabyte file twice is wasteful, so only the head of the file is probed.
"""
import codecs

SNIFF_BYTES = 2048

# order matters: cp932 accepts almost any byte sequence, so it must be tried last
CANDIDATES = ("utf-8", "cp932")


def _probe(head, enc):
    # the head may end in the middle of a multi-byte character: an incremental decoder
    # with final=False keeps an incomplete trailing sequence instead of failing on it
    try:
        codecs.getincrementaldecoder(enc)().decode(head, final=False)
        return True
    except UnicodeDecodeError:
        return False


def detect_encoding(data):
    """Return the codec name to use for the whole file."""
    if data.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    head = data[:SNIFF_BYTES]
    for enc in CANDIDATES:
        if _probe(head, enc):
            return enc
    return "latin-1"


def decode(data):
    """(text, encoding) for raw file bytes."""
    enc = detect_encoding(data)
    return data.decode(enc, errors="replace"), enc
