import hashlib
from models.canonical import CanonicalProfile, ProvenanceEntry
from core.confidence import calculate_field_confidence, calculate_overall_confidence
from adapters.base import AdapterResult

class MergeEngine:
    def merge_candidate(self, results: list[AdapterResult]) -> CanonicalProfile:
        provenance = []
        
        merged_data = {
            'full_name': '',
            'emails': [],
            'phones': [],
            'location': {},
            'links': {},
            'headline': None,
            'years_experience': None,
            'skills': [],
            'experience': [],
            'education': []
        }
        
        scalar_fields = ['full_name', 'headline', 'years_experience']
        dict_fields = ['location', 'links']
        list_fields = ['emails', 'phones', 'skills', 'experience', 'education']
        
        # Process scalar fields
        for field in scalar_fields:
            best_val = None
            best_conf = -1.0
            best_source = None
            
            for res in results:
                if field in res.raw_fields and res.raw_fields[field]:
                    val = res.raw_fields[field]
                    conf = calculate_field_confidence(val, res.trust_weight)
                    if conf > best_conf:
                        best_conf = conf
                        best_val = val
                        best_source = res.source_name
            
            if best_val is not None:
                merged_data[field] = best_val
                provenance.append(
                    ProvenanceEntry(
                        field=field, 
                        source=best_source, 
                        method='highest_confidence', 
                        confidence=best_conf
                    )
                )

        # Process dict fields
        for field in dict_fields:
            merged_dict = {}
            best_confs = {}
            best_sources = {}
            for res in results:
                if field in res.raw_fields and isinstance(res.raw_fields[field], dict):
                    for k, v in res.raw_fields[field].items():
                        if v is None or v == "":
                            continue
                        conf = calculate_field_confidence(v, res.trust_weight)
                        if conf > best_confs.get(k, -1.0):
                            best_confs[k] = conf
                            merged_dict[k] = v
                            best_sources[k] = res.source_name
                            
            merged_data[field] = merged_dict
            for k, conf in best_confs.items():
                provenance.append(
                    ProvenanceEntry(
                        field=field,
                        source=best_sources[k],
                        method='merge_keys',
                        confidence=conf
                    )
                )
        
        # Process list fields
        for field in list_fields:
            unique_items = []
            seen = set()
            
            for res in results:
                if field in res.raw_fields and isinstance(res.raw_fields[field], list) and res.raw_fields[field]:
                    # Add provenance once per source
                    conf = calculate_field_confidence(res.raw_fields[field], res.trust_weight)
                    provenance.append(
                        ProvenanceEntry(
                            field=field, 
                            source=res.source_name, 
                            method='union', 
                            confidence=conf
                        )
                    )
                    
                    for item in res.raw_fields[field]:
                        # Build a normalized dedup key
                        if isinstance(item, dict):
                            # For skill dicts, normalize on the 'name' key
                            name_val = item.get('name', '')
                            item_key = ('__dict__', name_val.strip().lower())
                        elif isinstance(item, str):
                            # Normalize strings: strip whitespace + lowercase
                            item_key = item.strip().lower()
                        else:
                            item_key = item
                            
                        if item_key not in seen:
                            seen.add(item_key)
                            # Store the item with whitespace stripped for strings
                            clean_item = item.strip() if isinstance(item, str) else item
                            unique_items.append(clean_item)
                            
            merged_data[field] = unique_items
            
        # Generate candidate_id
        if merged_data['emails']:
            primary = merged_data['emails'][0].lower()
            candidate_id = hashlib.sha256(primary.encode('utf-8')).hexdigest()
        else:
            full_name = merged_data.get('full_name', '').lower()
            candidate_id = hashlib.sha256(full_name.encode('utf-8')).hexdigest()
            
        merged_data['candidate_id'] = candidate_id
        
        # Calculate overall confidence
        conf_scores = [p.confidence for p in provenance]
        merged_data['overall_confidence'] = calculate_overall_confidence(conf_scores)
        merged_data['provenance'] = provenance
        
        return CanonicalProfile(**merged_data)
