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

        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', raw_text)
        email = email_match.group(0) if email_match else None

        phone_match = re.search(r'(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', raw_text)
        phone = phone_match.group(0) if phone_match else None

        urls = re.findall(r'https?://[^\s]+', raw_text)

        return {
            'raw_text': raw_text,
            'email': email,
            'phone': phone,
            'urls': urls
        }
