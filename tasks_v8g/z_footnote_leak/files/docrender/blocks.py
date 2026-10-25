"""Block-level node types produced by the parser."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Heading:
    level: int
    text: str


@dataclass
class Paragraph:
    text: str


@dataclass
class ListBlock:
    items: List[str] = field(default_factory=list)
    ordered: bool = False


@dataclass
class Code:
    lang: str
    lines: List[str] = field(default_factory=list)


@dataclass
class Rule:
    pass


@dataclass
class Document:
    blocks: list
    footnotes: dict   # id -> raw text of the definition
    links: dict       # name (lower case) -> url
