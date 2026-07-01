from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Any

class ProvenanceEntry(BaseModel):
    model_config = ConfigDict(strict=True)
    field: str
    source: str
    method: str
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_breakdown: Optional[Dict[str, float]] = None

class CanonicalProfile(BaseModel):
    model_config = ConfigDict(strict=True)
    candidate_id: str
    full_name: str
    emails: List[str]
    phones: List[str]
    location: Dict[str, str] = Field(default_factory=dict)
    links: Dict[str, str] = Field(default_factory=dict)
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    total_years_experience: float | None = None
    seniority_level: str | None = None
    average_tenure: float | None = None
    career_velocity: str | None = None
    executive_summary: str | None = None
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    conflicts_resolved: List[Dict[str, Any]] = Field(default_factory=list)
    provenance: List[ProvenanceEntry] = Field(default_factory=list)
    overall_confidence: float
