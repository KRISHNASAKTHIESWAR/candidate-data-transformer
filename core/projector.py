import logging
import re
from typing import Any
from models.canonical import CanonicalProfile
from models.config import RuntimeConfig

logger = logging.getLogger(__name__)

class Projector:
    @staticmethod
    def _resolve_path(data: dict, path: str) -> Any:
        current = data
        parts = path.split('.')
        
        for i, part in enumerate(parts):
            if current is None:
                return None
                
            # Check for array mapping e.g. skills[]
            if part.endswith('[]'):
                key = part[:-2]
                if not isinstance(current, dict) or key not in current:
                    return None
                
                lst = current[key]
                if not isinstance(lst, list):
                    return None
                    
                remaining_path = '.'.join(parts[i + 1:])
                if not remaining_path:
                    return lst
                
                mapped_list = []
                for item in lst:
                    if isinstance(item, dict):
                        val = Projector._resolve_path(item, remaining_path)
                        if val is not None:
                            mapped_list.append(val)
                return mapped_list
            
            # Check for list indexing e.g. emails[0]
            match = re.match(r'^([^\[]+)\[(\d+)\]$', part)
            if match:
                key = match.group(1)
                idx = int(match.group(2))
                if not isinstance(current, dict) or key not in current:
                    return None
                lst = current.get(key)
                if not isinstance(lst, list) or idx >= len(lst):
                    return None
                current = lst[idx]
            else:
                # Standard key
                if not isinstance(current, dict):
                    return None
                current = current.get(part)
                
        return current

    @staticmethod
    def apply(profile: CanonicalProfile, config: RuntimeConfig) -> dict:
        profile_dict = profile.model_dump()
        output_dict = {}
        
        for field in config.fields:
            fetch_path = field.from_ if field.from_ else field.path
            val = Projector._resolve_path(profile_dict, fetch_path)
            
            # Handle missing values
            # Considering empty strings, empty lists, empty dicts, or None as missing
            is_missing = val is None or val == "" or val == [] or val == {}
            
            if is_missing:
                if config.on_missing == 'omit':
                    continue
                elif config.on_missing == 'error':
                    logger.error(f"Missing required field: {fetch_path}")
                    raise ValueError(f"Missing required field: {fetch_path}")
                elif config.on_missing == 'null':
                    val = None
            
            # Apply Transformation
            if val is not None and not is_missing and field.transform:
                def transform_value(v):
                    if not isinstance(v, str):
                        return v
                    if field.transform == 'uppercase':
                        return v.upper()
                    elif field.transform == 'lowercase':
                        return v.lower()
                    elif field.transform == 'strip':
                        return v.strip()
                    return v

                if isinstance(val, list):
                    val = [transform_value(v) for v in val]
                else:
                    val = transform_value(val)
                    
            # Apply Normalization
            if val is not None and not is_missing and field.normalize:
                def apply_norm(v):
                    if field.normalize == 'E164' and isinstance(v, str):
                        # Attempt to dynamically determine region hint from profile location
                        country = profile_dict.get('location', {}).get('country', '')
                        region_hint = 'US'
                        if country:
                            country_upper = country.upper()
                            if country_upper in ['UK', 'UNITED KINGDOM']: region_hint = 'GB'
                            elif country_upper in ['INDIA']: region_hint = 'IN'
                            elif country_upper in ['GERMANY']: region_hint = 'DE'
                            elif country_upper in ['FRANCE']: region_hint = 'FR'
                            elif len(country_upper) == 2: region_hint = country_upper
                        
                        from core.normalizer import normalize_phone
                        normalized = normalize_phone(v, region_hint=region_hint)
                        return normalized if normalized else v
                    return v
                    
                if isinstance(val, list):
                    val = [apply_norm(v) for v in val]
                else:
                    val = apply_norm(val)
                    
            output_dict[field.path] = val
            
        # Confidence Toggle
        if config.include_confidence:
            output_dict['provenance'] = profile_dict.get('provenance', [])
            output_dict['overall_confidence'] = profile_dict.get('overall_confidence', 0.0)
            
        return output_dict
