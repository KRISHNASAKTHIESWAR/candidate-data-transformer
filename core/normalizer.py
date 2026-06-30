import logging
import json
import os
import phonenumbers
import dateutil.parser

logger = logging.getLogger(__name__)

alias_map_path = os.path.join(os.path.dirname(__file__), 'alias_map.json')
with open(alias_map_path, 'r', encoding='utf-8') as f:
    SKILL_ALIASES = json.load(f)

def normalize_phone(phone_str: str, region_hint: str = 'US') -> str | None:
    if not phone_str:
        return None
        
    try:
        parsed = phonenumbers.parse(phone_str, region_hint)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        else:
            logger.warning(f"Invalid phone number: {phone_str}")
            return None
    except phonenumbers.NumberParseException as e:
        logger.warning(f"Failed to parse phone number '{phone_str}': {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error parsing phone number '{phone_str}': {e}")
        return None

def normalize_date(date_str: str) -> str | None:
    if not date_str:
        return None
        
    lower_str = date_str.lower()
    if any(word in lower_str for word in ['present', 'current', 'now']):
        return None
        
    try:
        from datetime import datetime
        default_date = datetime(2000, 1, 1)
        parsed_date = dateutil.parser.parse(date_str, default=default_date)
        return parsed_date.strftime('%Y-%m')
    except Exception as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None

def normalize_skill(skill: str) -> str:
    if not skill:
        return skill
    lower_skill = skill.lower()
    if lower_skill in SKILL_ALIASES:
        return SKILL_ALIASES[lower_skill]
    return skill

def normalize_linkedin_url(url: str) -> str:
    if not url:
        return url
    
    # Strip query params
    url = url.split('?')[0]
    
    import re
    # Extract handle
    match = re.search(r'linkedin\.com/in/([^/]+)', url, re.IGNORECASE)
    if match:
        handle = match.group(1).strip()
        return f"https://www.linkedin.com/in/{handle}"
    return url
