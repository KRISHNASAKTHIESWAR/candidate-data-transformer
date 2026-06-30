def calculate_field_confidence(value, trust_weight: float) -> float:
    if value is None or (isinstance(value, str) and not value.strip()):
        return 0.0
    return trust_weight

def calculate_overall_confidence(confidences: list[float]) -> float:
    if not confidences:
        return 0.0
    return sum(confidences) / len(confidences)
