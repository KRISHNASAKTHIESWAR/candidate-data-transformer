import re
import pdfplumber
from adapters.base import BaseAdapter, AdapterResult

class PdfAdapter(BaseAdapter):
    def __init__(self):
        super().__init__(source_name='pdf_resume', trust_weight=0.65)
        
    def extract(self, source: str) -> dict:
        raw_text = ""
        
        # Safely open the PDF to ensure the file lock is released even if it crashes
        with pdfplumber.open(source) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    raw_text += text + "\n"
                
        # Clean rendering artifacts
        raw_text = re.sub(r'\(cid:\d+\)', '', raw_text)
        
        # Parsing Heuristics (Regex)
        
        # Extract and deduplicate emails
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', raw_text)
        extracted_emails = list(set(emails))
        
        # Extract and deduplicate phones
        phones = re.findall(r'(?:\+?\d{1,3}[\s.-]?)?\(?\d{2,5}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,5}', raw_text)
        extracted_phones = list(set(phones))
        
        # Heuristic for Name: First non-empty line of the resume
        extracted_name = None
        lines = raw_text.split('\n')
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        if non_empty_lines:
            extracted_name = non_empty_lines[0].title()
            
        # Package and Return
        parsed_data = {
            'full_name': extracted_name,
            'emails': extracted_emails,
            'phones': extracted_phones
        }
        
        return parsed_data
