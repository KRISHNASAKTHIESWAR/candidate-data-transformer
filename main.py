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

import re
from core.normalizer import normalize_skill

# --- Field name normalization maps per source ---
# Maps raw adapter keys -> canonical CanonicalProfile field names
CSV_FIELD_MAP = {
    'name': 'full_name',
    'email': 'emails',       # will be wrapped in a list
    'phone': 'phones',       # will be wrapped in a list
    'title': 'experience_title',
    'current company': 'experience_company',
}

ATS_FIELD_MAP = {
    'applicant_id': 'candidate_id',
    'applicant_name': 'full_name',
    'contact': 'emails',     # will be wrapped in a list
    'role': 'headline',
    'skills_list': 'skills', # will be converted to [{name: ...}] dicts
    'linkedin_url': 'links_linkedin',
    'github_url': 'links_github',
}

NOTES_FIELD_MAP = {
    'applicant_id': 'candidate_id',
    'email': 'emails',       # will be wrapped in a list
    'phone': 'phones',       # will be wrapped in a list
}

def normalize_csv_row(row: dict) -> dict:
    """Remap a raw CSV row dict to canonical field names."""
    out = {}
    lower_row = {k.lower().strip(): v for k, v in row.items()}
    exp_entry = {}
    for src_key, canon_key in CSV_FIELD_MAP.items():
        val = lower_row.get(src_key)
        if not val or not str(val).strip():
            continue
        val = str(val).strip()
        if canon_key in ('emails', 'phones'):
            out[canon_key] = [val]
        elif canon_key == 'experience_title':
            exp_entry['title'] = val
        elif canon_key == 'experience_company':
            exp_entry['company'] = val
        else:
            out[canon_key] = val
    if exp_entry:
        out['experience'] = [exp_entry]
    return out

def normalize_ats_record(record: dict) -> dict:
    """Remap a raw ATS JSON record to canonical field names."""
    out = {}
    links = {}
    for src_key, canon_key in ATS_FIELD_MAP.items():
        val = record.get(src_key)
        if val is None or val == '' or val == []:
            continue
        if canon_key == 'emails':
            out[canon_key] = [str(val).strip()]
        elif canon_key == 'skills':
            # Convert list of skill strings to list of dicts with canonical names
            out[canon_key] = [{'name': normalize_skill(s.strip())} for s in val if s and str(s).strip()]
        elif canon_key == 'links_linkedin':
            links['linkedin'] = str(val).strip()
        elif canon_key == 'links_github':
            links['github'] = str(val).strip()
        else:
            out[canon_key] = str(val).strip() if isinstance(val, str) else val
            
    if links:
        out['links'] = links
    return out

def normalize_notes_record(raw: dict) -> dict:
    """Remap notes adapter fields to canonical field names."""
    out = {}
    raw_text = raw.get('raw_text', '')
    if raw_text:
        out['raw_text'] = raw_text
        
        # Regex for github and linkedin (without requiring http://, and ignoring trailing punctuation)
        github_match = re.search(r'(?:https?://)?(?:www\.)?(github\.com/[A-Za-z0-9_-]+)', raw_text, re.IGNORECASE)
        linkedin_match = re.search(r'(?:https?://)?(?:www\.)?(linkedin\.com/in/[A-Za-z0-9_-]+)', raw_text, re.IGNORECASE)
        links = {}
        if github_match: links['github'] = "https://" + github_match.group(1)
        if linkedin_match: links['linkedin'] = "https://" + linkedin_match.group(1)
        if links: out['links'] = links
        
        # Regex for years of experience
        exp_match = re.search(r'(\d+(?:[.-]\d+)?\+?)\s*(?:yrs|years)\s*exp', raw_text, re.IGNORECASE)
        if exp_match:
            raw_exp = exp_match.group(1)
            # robustly extract the first number from something like "6+", "6-7", "6.5"
            num_match = re.search(r'(\d+(?:\.\d+)?)', raw_exp)
            if num_match:
                try:
                    out['years_experience'] = float(num_match.group(1))
                except ValueError:
                    pass
                
        # Regex for education/degree
        degree_match = re.search(r'(CS degree|PhD|master\'s|bachelor\'s)', raw_text, re.IGNORECASE)
        if degree_match:
            out['education'] = [{'degree': degree_match.group(1)}]
            
        # Regex for company (Currently at X, works at X, now at X, moved to X)
        company_match = re.search(r'(?:Currently at|at|now at|moved to) ([A-Z][a-zA-Z0-9]+)', raw_text)
        if company_match:
            out['experience'] = [{'company': company_match.group(1), '_is_current_override': True}]

    for src_key, canon_key in NOTES_FIELD_MAP.items():
        val = raw.get(src_key)
        if not val:
            continue
        if canon_key in ('emails', 'phones'):
            out[canon_key] = [str(val).strip()]
        else:
            out[canon_key] = str(val).strip()
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

def main():
    parser = argparse.ArgumentParser(description="Candidate Data Transformer")
    parser.add_argument('--input_dir', type=str, default='sample_input_new', help="Directory containing raw files")
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
    exploded = []
    
    for res in raw_results:
        # Ignore completely failed extractions that returned empty dict
        if not res.raw_fields:
            continue
            
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

        elif source == 'recruiter_notes' and 'records' in raw:
            # Notes: process each record from the file
            for record in raw['records']:
                normed = normalize_notes_record(record)
                if normed:
                    exploded.append(AdapterResult(
                        raw_fields=normed,
                        source_name=res.source_name,
                        trust_weight=res.trust_weight,
                        error=res.error
                    ))
        else:
            exploded.append(res)
            
    # Remove flagged records and extract grouping keys
    valid_exploded = []
    for ext_res in exploded:
        raw_text = ext_res.raw_fields.get('raw_text', '')
        if raw_text and is_flagged_record(raw_text):
            logger.warning("Flagged record detected (DO NOT PROCESS): skipping.")
            continue
        valid_exploded.append(ext_res)

    # Grouping with Collision Guard
    grouped_candidates = {}
    name_to_group_key = {}
    email_to_group_key = {}
    app_id_to_group_key = {}
    counter = 0
    
    for res in valid_exploded:
        raw = res.raw_fields
        
        # Extract email
        email = None
        if raw.get('email'):
            email = str(raw['email']).strip().lower()
        elif raw.get('emails') and isinstance(raw['emails'], list) and len(raw['emails']) > 0:
            email = str(raw['emails'][0]).strip().lower()
            
        # Extract name
        name = None
        if raw.get('full_name'):
            name = str(raw['full_name']).strip().lower()
        elif raw.get('name'):
            name = str(raw['name']).strip().lower()
            
        # Extract ID
        app_id = None
        if raw.get('candidate_id'):
            app_id = str(raw['candidate_id']).strip().upper()
        elif raw.get('applicant_id'):
            app_id = str(raw['applicant_id']).strip().upper()
            
        # Determine base grouping key
        group_key = None
        if app_id and app_id in app_id_to_group_key:
            group_key = app_id_to_group_key[app_id]
        elif email and email in email_to_group_key:
            group_key = email_to_group_key[email]
        elif app_id:
            group_key = app_id
        elif email:
            group_key = email
        elif name:
            group_key = name
        else:
            group_key = f"unknown_{counter}"
            counter += 1

        # Collision Guard Logic
        if name and email:
            if name in name_to_group_key:
                existing_key = name_to_group_key[name]
                existing_group = grouped_candidates.get(existing_key, [])
                
                # Check email of existing group
                existing_email = None
                for existing_res in existing_group:
                    ex_raw = existing_res.raw_fields
                    if ex_raw.get('email'):
                        existing_email = str(ex_raw['email']).strip().lower()
                        break
                    elif ex_raw.get('emails') and isinstance(ex_raw['emails'], list) and len(ex_raw['emails']) > 0:
                        existing_email = str(ex_raw['emails'][0]).strip().lower()
                        break
                
                if existing_email and existing_email != email:
                    logger.warning(f"WARNING: Potential duplicate identity detected for {name}. Keeping profiles separate due to conflicting emails.")
                    group_key = f"{name}_{counter}"
                    counter += 1
                else:
                    # No collision, merge into existing group
                    group_key = existing_key
            else:
                # Store the primary group key for this name
                name_to_group_key[name] = group_key

        if app_id:
            app_id_to_group_key[app_id] = group_key
        if email:
            email_to_group_key[email] = group_key

        if group_key not in grouped_candidates:
            grouped_candidates[group_key] = []
        grouped_candidates[group_key].append(res)

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
