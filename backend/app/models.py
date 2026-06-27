from typing import Literal, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

class ElementBase(BaseModel):
    """Base schema ensuring spatial awareness and confidence scoring."""
    bbox: Optional[Tuple[float, float, float, float]] = None
    confidence: Optional[float] = 100.0  
    metadata: dict[str, Any] = Field(default_factory=dict)

class Heading(ElementBase):
    type: Literal["heading"] = "heading"
    level: int = 1
    text: str

class Paragraph(ElementBase):
    type: Literal["paragraph"] = "paragraph"
    text: str

class Table(ElementBase):
    type: Literal["table"] = "table"
    headers: List[Optional[str]] = Field(default_factory=list)
    rows: List[List[Optional[str]]]

class ListGroup(ElementBase):
    type: Literal["list"] = "list"
    items: List[str]

class OcrText(ElementBase):
    type: Literal["ocr_text"] = "ocr_text"
    text: str

DocumentElement = Union[Heading, Paragraph, Table, ListGroup, OcrText]

class Page(BaseModel):
    number: int
    elements: List[DocumentElement] = Field(default_factory=list)
    requires_ocr: bool = False
    low_quality: bool = False

class NormalizedDocument(BaseModel):
    filename: str
    pages: List[Page] = Field(default_factory=list)
    ocr_used: bool = False          
    low_quality: bool = False       
    metadata: dict[str, Any] = Field(default_factory=dict)