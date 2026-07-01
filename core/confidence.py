from typing import Any

FIELD_TRUST = {
    "emails":           {"recruiter_csv": 0.90, "ats_json": 0.85, "pdf_resume": 0.70, "recruiter_notes": 0.40},
    "phones":           {"recruiter_csv": 0.90, "ats_json": 0.85, "pdf_resume": 0.65, "recruiter_notes": 0.40},
    "skills":           {"recruiter_notes": 0.85, "pdf_resume": 0.75, "ats_json": 0.60, "recruiter_csv": 0.50},
    "experience":       {"pdf_resume": 0.85, "recruiter_notes": 0.80, "ats_json": 0.70, "recruiter_csv": 0.40},
    "years_experience": {"pdf_resume": 0.85, "recruiter_notes": 0.80, "ats_json": 0.70, "recruiter_csv": 0.40},
    "full_name":        {"recruiter_csv": 0.85, "ats_json": 0.80, "pdf_resume": 0.75, "recruiter_notes": 0.55}
}

def calculate_field_confidence(field: str, value: Any, sources: list[str], fallback_weight: float) -> dict:
    # Normalize field name variations (e.g., email vs emails)
    canon_field = field
    if field == "email": canon_field = "emails"
    elif field == "phone": canon_field = "phones"

    breakdown = {}
    primary_source = sources[0] if sources else "unknown"
    
    # 1. Base trust
    breakdown["base"] = FIELD_TRUST.get(canon_field, {}).get(primary_source, fallback_weight)
    
    # 2. Format validation
    val_str = str(value) if value is not None else ""
    if canon_field == "emails":
        breakdown["format"] = 1.10 if "@" in val_str else 0.60
    elif canon_field == "phones":
        breakdown["format"] = 1.10 if val_str.startswith("+") else 0.70
    else:
        breakdown["format"] = 1.0
        
    # 3. Cross-source agreement
    breakdown["agreement"] = 1.20 if len(set(sources)) > 1 else 1.0
    
    # 4. Value completeness
    breakdown["completeness"] = 1.10 if val_str and len(val_str.strip()) > 2 else 0.80
    
    final_score = (breakdown["base"] 
                   * breakdown["format"] 
                   * breakdown["agreement"] 
                   * breakdown["completeness"])
    
    return {
        "score": min(round(final_score, 2), 0.95),
        "breakdown": breakdown
    }

def calculate_overall_confidence(confidences: list[float]) -> float:
    if not confidences:
        return 0.0
    return sum(confidences) / len(confidences)
