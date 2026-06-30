import abc
import dataclasses
import sys
from typing import Any


@dataclasses.dataclass
class AdapterResult:
    raw_fields: dict
    source_name: str
    trust_weight: float
    error: str | None


class BaseAdapter(abc.ABC):
    def __init__(self, source_name: str, trust_weight: float):
        self.source_name = source_name
        self.trust_weight = trust_weight

    @abc.abstractmethod
    def extract(self, source: Any) -> dict:
        pass

    def safe_extract(self, source: Any) -> AdapterResult:
        try:
            raw_fields = self.extract(source)
            return AdapterResult(
                raw_fields=raw_fields,
                source_name=self.source_name,
                trust_weight=self.trust_weight,
                error=None
            )
        except Exception as e:
            error_msg = str(e)
            print(error_msg, file=sys.stderr)
            return AdapterResult(
                raw_fields={},
                source_name=self.source_name,
                trust_weight=0.0,
                error=error_msg
            )
