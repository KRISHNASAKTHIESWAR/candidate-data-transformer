import re
import os
from adapters.base import BaseAdapter, AdapterResult

class NotesAdapter(BaseAdapter):
    def __init__(self, trust_weight: float = 0.50):
        super().__init__(source_name='recruiter_notes', trust_weight=trust_weight)

    def extract(self, source_path: str) -> dict:
        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
        except FileNotFoundError:
            return {}

        records = []
        # Find all chunks using the AT-xxxx marker
        chunks = re.finditer(r'===\s*(AT-\d+)\s*===', raw_text)
        chunk_list = list(chunks)
        
        for i, match in enumerate(chunk_list):
            applicant_id = match.group(1)
            start_idx = match.end()
            end_idx = chunk_list[i+1].start() if i + 1 < len(chunk_list) else len(raw_text)
            chunk = raw_text[start_idx:end_idx].strip()
            
            if not chunk:
                continue
                
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', chunk)
            email = email_match.group(0) if email_match else None

            phone_match = re.search(r'(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', chunk)
            phone = phone_match.group(0) if phone_match else None

            urls = re.findall(r'https?://[^\s]+', chunk)

            records.append({
                'applicant_id': applicant_id,
                'raw_text': chunk,
                'email': email,
                'phone': phone,
                'urls': urls
            })

        return {'records': records}
