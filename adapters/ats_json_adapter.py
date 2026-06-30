import json
from adapters.base import BaseAdapter, AdapterResult

class AtsJsonAdapter(BaseAdapter):
    def __init__(self, trust_weight: float = 0.85):
        super().__init__(source_name='ats_json', trust_weight=trust_weight)

    def _get_nested_value(self, data: dict, path: str):
        keys = path.split('.')
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    def extract(self, source_path: str) -> dict:
        with open(source_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
