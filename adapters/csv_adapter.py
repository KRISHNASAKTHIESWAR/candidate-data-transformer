import csv
from adapters.base import BaseAdapter, AdapterResult

class CsvAdapter(BaseAdapter):
    def __init__(self, trust_weight: float = 0.85):
        super().__init__(source_name='recruiter_csv', trust_weight=trust_weight)

    def extract(self, source_path: str) -> dict:
        with open(source_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            if not rows:
                return {}
            
            return {'rows': rows}
