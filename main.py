import argparse
import json
import os
import sys
from pathlib import Path
import logging

from adapters.csv_adapter import CsvAdapter
from adapters.ats_json_adapter import AtsJsonAdapter
from adapters.notes_adapter import NotesAdapter
from adapters.base import AdapterResult
from core.merger import MergeEngine
from core.projector import Projector
from models.config import RuntimeConfig

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- Field name normalization maps per source ---
# Maps raw adapter keys -> canonical CanonicalProfile field names
CSV_FIELD_MAP = {
    'name': 'full_name',
    'email': 'emails',       # will be wrapped in a list
    'phone': 'phones',       # will be wrapped in a list
    'title': 'headline',
    'current company': 'headline',  # fallback if title missing
}

ATS_FIELD_MAP = {
    'applicant_name': 'full_name',
    'contact': 'emails',     # will be wrapped in a list
    'role': 'headline',
    'skills_list': 'skills', # will be converted to [{name: ...}] dicts
}

NOTES_FIELD_MAP = {
    'email': 'emails',       # will be wrapped in a list
    'phone': 'phones',       # will be wrapped in a list
}

def normalize_csv_row(row: dict) -> dict:
    """Remap a raw CSV row dict to canonical field names."""
    out = {}
    lower_row = {k.lower().strip(): v for k, v in row.items()}
    for src_key, canon_key in CSV_FIELD_MAP.items():
        val = lower_row.get(src_key)
        if not val or not str(val).strip():
            continue
        val = str(val).strip()
        if canon_key in ('emails', 'phones'):
            out[canon_key] = [val]
        else:
            out[canon_key] = val
    return out

def normalize_ats_record(record: dict) -> dict:
    """Remap a raw ATS JSON record to canonical field names."""
    out = {}
    for src_key, canon_key in ATS_FIELD_MAP.items():
        val = record.get(src_key)
        if val is None or val == '' or val == []:
            continue
        if canon_key == 'emails':
            out[canon_key] = [str(val).strip()]
        elif canon_key == 'skills':
            # Convert list of skill strings to list of dicts
            out[canon_key] = [{'name': s} for s in val if s and str(s).strip()]
        else:
            out[canon_key] = str(val).strip() if isinstance(val, str) else val
    return out

def normalize_notes_record(raw: dict) -> dict:
    """Remap notes adapter fields to canonical field names."""
    out = {}
    if raw.get('raw_text'):
        out['raw_text'] = raw['raw_text']
    for src_key, canon_key in NOTES_FIELD_MAP.items():
        val = raw.get(src_key)
        if not val:
            continue
        out[canon_key] = [str(val).strip()]
    return out

# Phrases that indicate a record should be excluded from processing
_DO_NOT_PROCESS_PHRASES = [
    'do not process',
    'do not send',
    'test row',
    'flag and exclude',
    'test record',
]

def is_flagged_record(raw_text: str) -> bool:
    """Return True if the notes text explicitly says to skip this record."""
    lower = raw_text.lower()
    return any(phrase in lower for phrase in _DO_NOT_PROCESS_PHRASES)

def extract_grouping_key(raw) -> str:
    """Heuristically find an email or name to group candidates by."""
    # Handle case where 'raw' is a list of objects/records instead of a single dict
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                key = extract_grouping_key(item)
                if key != "unknown":
                    return key
        return "unknown"

    # Ensure raw is a dictionary before proceeding
    if not isinstance(raw, dict):
        return "unknown"

    # 1. Try to find an email
    if raw.get('email'):
        return str(raw['email']).strip().lower()
    if raw.get('emails') and isinstance(raw['emails'], list) and len(raw['emails']) > 0:
        return str(raw['emails'][0]).strip().lower()
    if raw.get('applicant') and isinstance(raw['applicant'], dict):
        contact = raw['applicant'].get('contact', {})
        if contact.get('email'):
            return str(contact['email']).strip().lower()
            
    # 2. Fallback to name
    if raw.get('full_name'):
        return str(raw['full_name']).strip().lower()
    if raw.get('name'):
        return str(raw['name']).strip().lower()
    if raw.get('applicant') and isinstance(raw['applicant'], dict):
        if raw['applicant'].get('name'):
            return str(raw['applicant']['name']).strip().lower()
            
    return "unknown"

def main():
    parser = argparse.ArgumentParser(description="Candidate Data Transformer")
    parser.add_argument('--input_dir', type=str, default='sample_inputs', help="Directory containing raw files")
    parser.add_argument('--config', type=str, default='config.json', help="Path to config JSON file")
    parser.add_argument('--output', type=str, default='output.json', help="Path to write final JSON")
    args = parser.parse_args()

    # Load Config
    if not os.path.exists(args.config):
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)
        
    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        config = RuntimeConfig(**config_data)
    except Exception as e:
        logger.error(f"Failed to parse configuration: {e}")
        sys.exit(1)

    # Ingestion Layer
    input_path = Path(args.input_dir)
    if not input_path.exists() or not input_path.is_dir():
        logger.error(f"Input directory not found: {args.input_dir}")
        sys.exit(1)

    raw_results = []
    csv_adapter = CsvAdapter()
    json_adapter = AtsJsonAdapter()
    notes_adapter = NotesAdapter()

    for file_path in input_path.iterdir():
        if not file_path.is_file():
            continue
            
        ext = file_path.suffix.lower()
        if ext == '.csv':
            raw_results.append(csv_adapter.safe_extract(str(file_path)))
        elif ext == '.json':
            raw_results.append(json_adapter.safe_extract(str(file_path)))
        elif ext == '.txt':
            raw_results.append(notes_adapter.safe_extract(str(file_path)))
        else:
            logger.info(f"Skipping unsupported file type: {file_path}")

    # Explode & Group
    grouped_candidates = {}
    
    for res in raw_results:
        # Ignore completely failed extractions that returned empty dict
        if not res.raw_fields:
            continue
            
        exploded = []
        raw = res.raw_fields
        source = res.source_name
        
        if source == 'recruiter_csv' and 'rows' in raw:
            # CSV: explode rows and normalize each
            for row in raw['rows']:
                if not any(v and str(v).strip() for v in row.values()):
                    continue  # skip fully empty rows
                normed = normalize_csv_row(row)
                if normed:
                    exploded.append(AdapterResult(
                        raw_fields=normed,
                        source_name=res.source_name,
                        trust_weight=res.trust_weight,
                        error=res.error
                    ))

        elif source == 'ats_json':
            # ATS JSON: root may be a list of records or a single dict
            records = raw if isinstance(raw, list) else [raw]
            for record in records:
                if not isinstance(record, dict):
                    continue
                normed = normalize_ats_record(record)
                if normed:
                    exploded.append(AdapterResult(
                        raw_fields=normed,
                        source_name=res.source_name,
                        trust_weight=res.trust_weight,
                        error=res.error
                    ))

        elif source == 'recruiter_notes':
            # Notes: normalize field names
            normed = normalize_notes_record(raw)
            if normed:
                exploded.append(AdapterResult(
                    raw_fields=normed,
                    source_name=res.source_name,
                    trust_weight=res.trust_weight,
                    error=res.error
                ))
        else:
            exploded.append(res)
            
        for ext_res in exploded:
            # Check if notes explicitly flag this record as do-not-process
            raw_text = ext_res.raw_fields.get('raw_text', '')
            if raw_text and is_flagged_record(raw_text):
                logger.warning(f"Flagged record detected (DO NOT PROCESS): skipping grouping key lookup, "
                               f"will be tagged in output.")
                ext_res = AdapterResult(
                    raw_fields={**ext_res.raw_fields, '_flagged': True},
                    source_name=ext_res.source_name,
                    trust_weight=0.0,
                    error='DO_NOT_PROCESS flag detected in recruiter notes'
                )

            grouping_key = extract_grouping_key(ext_res.raw_fields)
            if grouping_key not in grouped_candidates:
                grouped_candidates[grouping_key] = []
            grouped_candidates[grouping_key].append(ext_res)

    # Merge & Project
    engine = MergeEngine()
    final_output = []

    for group_key, results_list in grouped_candidates.items():
        if group_key == "unknown" and not any(r.raw_fields for r in results_list):
            continue  # Skip garbage empty results

        # Skip groups where ALL results are flagged as DO NOT PROCESS
        if all(r.raw_fields.get('_flagged') for r in results_list):
            logger.warning(f"Skipping fully-flagged candidate group: '{group_key}'")
            continue

        try:
            profile = engine.merge_candidate(results_list)
            final_dict = Projector.apply(profile, config)
            final_output.append(final_dict)
        except Exception as e:
            logger.error(f"Failed to process candidate group '{group_key}': {e}")

    # Export
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=2)
        logger.info(f"Successfully wrote {len(final_output)} candidate(s) to {args.output}")
    except Exception as e:
        logger.error(f"Failed to write output file: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
