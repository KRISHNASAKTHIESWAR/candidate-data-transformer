from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal

class ConfigField(BaseModel):
    model_config = ConfigDict(strict=True, populate_by_name=True)
    path: str
    from_: Optional[str] = Field(default=None, alias='from')
    type: str
    required: bool
    normalize: Optional[str] = None
    transform: Optional[str] = None

class RuntimeConfig(BaseModel):
    model_config = ConfigDict(strict=True)
    fields: List[ConfigField]
    include_confidence: bool
    on_missing: Literal['null', 'omit', 'error']
