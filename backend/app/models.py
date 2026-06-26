from dataclasses import dataclass, field, asdict
from typing import Literal, Any, List, Optional, Tuple

@dataclass(kw_only=True)
class Element:
    """Base class for all document elements to ensure consistent metadata."""
    type: Literal["heading", "paragraph", "table", "list", "image", "ocr_text"]
    page: int
    bbox: Optional[Tuple[float, float, float, float]] = None
    confidence: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(kw_only=True)
class Heading(Element):
    level: int
    text: str

@dataclass(kw_only=True)
class Paragraph(Element):
    text: str

@dataclass(kw_only=True)
class Table(Element):
    rows: List[List[Optional[str]]]

@dataclass(kw_only=True)
class ListGroup(Element):
    items: List[str]

@dataclass(kw_only=True)
class Page:
    number: int
    elements: List[Element] = field(default_factory=list)

@dataclass(kw_only=True)
class NormalizedDocument:
    filename: str
    pages: List[Page] = field(default_factory=list)
    ocr_used: bool = False
    low_quality: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)