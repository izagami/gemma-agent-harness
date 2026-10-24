"""Plain data objects shared by the reader, the deduplicator and the store."""
from dataclasses import dataclass, field


@dataclass
class Record:
    """One row of a vendor file after column mapping."""
    source: str          # "<vendor>:<vendor's customer id>"
    name: str = ""
    email: str = ""
    phone: str = ""
    line: int = 0        # 1-based line number in the vendor file (for messages)


@dataclass
class Customer:
    id: int
    name: str
    email: str = ""
    phone: str = ""
    sources: list = field(default_factory=list)

    def to_json(self):
        return {"id": self.id, "name": self.name, "email": self.email,
                "phone": self.phone, "sources": list(self.sources)}

    @classmethod
    def from_json(cls, d):
        return cls(d["id"], d["name"], d.get("email", ""), d.get("phone", ""), list(d.get("sources", [])))
