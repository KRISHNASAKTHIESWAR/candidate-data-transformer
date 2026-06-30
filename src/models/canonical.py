from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Any

class ProvenanceEntry(BaseModel):
    model_config = ConfigDict(strict=True)
    field: str
    source: str
    method: str
    confidence: float = Field(ge=0.0, le=1.0)

class CanonicalProfile(BaseModel):
    model_config = ConfigDict(strict=True)
    candidate_id: str
    full_name: str
    emails: List[str]
    phones: List[str]
    location: Dict[str, str]
    links: Dict[str, str]
    headline: Optional[str]
    years_experience: Optional[float]
    skills: List[Dict[str, Any]]
    experience: List[Dict[str, Any]]
    education: List[Dict[str, Any]]
    provenance: List[ProvenanceEntry]
    overall_confidence: float
