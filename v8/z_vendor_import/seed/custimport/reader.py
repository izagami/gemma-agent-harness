"""Read a vendor CSV file into Record objects."""
import csv
import io
import os

from custimport import normalize, sniff
from custimport.model import Record

# vendor header spellings -> our field names
COLUMNS = {
    "id": "vid", "customer_no": "vid", "顧客id": "vid", "顧客番号": "vid",
    "name": "name", "full_name": "name", "氏名": "name", "顧客名": "name",
    "email": "email", "mail": "email", "メール": "email", "メールアドレス": "email",
    "phone": "phone", "tel": "phone", "電話": "phone", "電話番号": "phone",
}


class ReadError(Exception):
    pass


def vendor_of(path):
    """vendor name = file name without extension ("data/vendor_b.csv" -> "vendor_b")."""
    return os.path.splitext(os.path.basename(path))[0]


def map_header(header):
    """List of field names (or None for ignored columns), one per CSV column."""
    out = []
    for h in header:
        out.append(COLUMNS.get(h.strip().lower()))
    if "vid" not in out:
        raise ReadError("no customer id column in header: " + ",".join(header))
    return out


def parse(text, vendor):
    rows = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(rows)
    except StopIteration:
        return []
    fields = map_header(header)
    records = []
    for n, row in enumerate(rows, start=2):
        if not any(c.strip() for c in row):
            continue
        values = {}
        for f, v in zip(fields, row):
            if f:
                values[f] = v
        vid = values.get("vid", "").strip()
        if not vid:
            raise ReadError(f"{vendor}: line {n}: empty customer id")
        records.append(Record(
            source=f"{vendor}:{vid}",
            name=normalize.clean_name(values.get("name", "")),
            email=normalize.clean_email(values.get("email", "")),
            phone=normalize.clean_phone(values.get("phone", "")),
            line=n,
        ))
    return records


def read_file(path):
    """(records, encoding) for one vendor file."""
    with open(path, "rb") as f:
        data = f.read()
    text, enc = sniff.decode(data)
    return parse(text, vendor_of(path)), enc
