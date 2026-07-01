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
            'education': [],
            'aliases': []
        }
        
        scalar_fields = ['full_name', 'headline', 'years_experience']
        dict_fields = ['location', 'links']
        list_fields = ['emails', 'phones', 'skills', 'experience', 'education']
        
        # Process scalar fields
        for field in scalar_fields:
            best_val = None
            best_conf = -1.0
            best_source = None
            best_breakdown = None
            
            aliases_collected = set()
            field_values = []
            
            for res in results:
                if field in res.raw_fields and res.raw_fields[field]:
                    val = res.raw_fields[field]
                    if isinstance(val, str):
                        val = val.strip()
                    if not val:
                        continue
                        
                    agreeing_sources = []
                    val_lower = val.lower() if isinstance(val, str) else val
                    for r in results:
                        if field in r.raw_fields and r.raw_fields[field]:
                            cmp_val = r.raw_fields[field]
                            if isinstance(cmp_val, str):
                                cmp_val = cmp_val.strip()
                            cmp_val_lower = cmp_val.lower() if isinstance(cmp_val, str) else cmp_val
                            if val_lower == cmp_val_lower:
                                agreeing_sources.append(r.source_name)
                                
                    conf_res = calculate_field_confidence(field, val, agreeing_sources, res.trust_weight)
                    conf = conf_res['score']
                    field_values.append({'val': val, 'conf': conf, 'source': res.source_name})
                    
                    if conf > best_conf:
                        if best_val is not None and field == 'full_name' and best_val.lower() != val.lower():
                            aliases_collected.add(best_val)
                        best_conf = conf
                        best_val = val
                        best_source = res.source_name
                        best_breakdown = conf_res['breakdown']
                    elif field == 'full_name' and best_val is not None and val.lower() != best_val.lower():
                        aliases_collected.add(val)
            
            # Detect conflicts for this scalar field
            if len(field_values) > 1:
                for fv in field_values:
                    # Case-insensitive comparison for strings, exact for others
                    if isinstance(best_val, str) and isinstance(fv['val'], str):
                        is_diff = best_val.lower() != fv['val'].lower()
                    else:
                        is_diff = best_val != fv['val']
                        
                    if is_diff:
                        if 'conflicts_resolved' not in merged_data:
                            merged_data['conflicts_resolved'] = []
                        merged_data['conflicts_resolved'].append({
                            'field': field,
                            'winning_value': best_val,
                            'losing_value': fv['val'],
                            'winning_source': best_source,
                            'losing_source': fv['source']
                        })
            
            if field == 'full_name' and aliases_collected:
                merged_data['aliases'] = list(aliases_collected)
            
            if best_val is not None:
                merged_data[field] = best_val
                provenance.append(
                    ProvenanceEntry(
                        field=field, 
                        source=best_source, 
                        method='highest_confidence', 
                        confidence=best_conf,
                        confidence_breakdown=best_breakdown
                    )
                )
                
        # Process dict fields
        for field in dict_fields:
            merged_dict = {}
            best_confs = {}
            best_sources = {}
            best_breakdowns = {}
            for res in results:
                if field in res.raw_fields and isinstance(res.raw_fields[field], dict):
                    for k, v in res.raw_fields[field].items():
                        if v is None or v == "":
                            continue
                            
                        agreeing_sources = []
                        v_lower = v.lower() if isinstance(v, str) else v
                        for r in results:
                            if field in r.raw_fields and isinstance(r.raw_fields[field], dict):
                                if k in r.raw_fields[field] and r.raw_fields[field][k]:
                                    cmp_v = r.raw_fields[field][k]
                                    cmp_v_lower = cmp_v.lower() if isinstance(cmp_v, str) else cmp_v
                                    if v_lower == cmp_v_lower:
                                        agreeing_sources.append(r.source_name)
                                        
                        conf_res = calculate_field_confidence(field, v, agreeing_sources, res.trust_weight)
                        conf = conf_res['score']
                        if conf > best_confs.get(k, -1.0):
                            best_confs[k] = conf
                            merged_dict[k] = v
                            best_sources[k] = res.source_name
                            best_breakdowns[k] = conf_res['breakdown']
                            
            merged_data[field] = merged_dict
            for k, conf in best_confs.items():
                provenance.append(
                    ProvenanceEntry(
                        field=field,
                        source=best_sources[k],
                        method='merge_keys',
                        confidence=conf,
                        confidence_breakdown=best_breakdowns[k]
                    )
                )
        
        # Process list fields
        for field in list_fields:
            unique_items = []
            seen = set()
            
            for res in results:
                if field in res.raw_fields and isinstance(res.raw_fields[field], list) and res.raw_fields[field]:
                    # Add provenance once per source
                    conf_res = calculate_field_confidence(field, res.raw_fields[field], [res.source_name], res.trust_weight)
                    conf = conf_res['score']
                    provenance.append(
                        ProvenanceEntry(
                            field=field, 
                            source=res.source_name, 
                            method='union', 
                            confidence=conf,
                            confidence_breakdown=conf_res['breakdown']
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
                            
            # Sort unique items if any have a recency override
            if unique_items and isinstance(unique_items[0], dict):
                unique_items.sort(key=lambda x: not x.get('_is_current_override', False))
                            
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
