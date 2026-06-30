"""
core/reasoner.py

Generates human-readable reasoning narratives for each decision the
MergeEngine made when processing a candidate.  Works entirely from
the provenance list already embedded in the output dict, so no extra
pipeline pass is required.
"""
from __future__ import annotations

from typing import Any


# ── Confidence buckets ──────────────────────────────────────────────────────

def _confidence_label(score: float) -> str:
    if score >= 0.80:
        return "HIGH"
    elif score >= 0.60:
        return "MEDIUM"
    else:
        return "LOW"


# ── Field-level narrative helpers ────────────────────────────────────────────

def _sources_for_field(provenance: list[dict], field: str) -> list[dict]:
    return [p for p in provenance if p.get("field") == field]


def _describe_scalar(field: str, provenance: list[dict]) -> str | None:
    entries = _sources_for_field(provenance, field)
    if not entries:
        return None
    winner = max(entries, key=lambda p: p["confidence"])
    label = _confidence_label(winner["confidence"])
    return (
        f"'{field}' was resolved from ({winner['source']}) "
        f"with {label} confidence ({winner['confidence']:.2f}). "
        f"Method: {winner['method']}."
    )


def _describe_list_field(field: str, provenance: list[dict]) -> str | None:
    entries = _sources_for_field(provenance, field)
    if not entries:
        return None
    sources = list(dict.fromkeys(p["source"] for p in entries))  # ordered unique
    count = len(entries)
    avg_conf = sum(p["confidence"] for p in entries) / count
    label = _confidence_label(avg_conf)
    return (
        f"'{field}' was unioned from {count} item(s) across "
        f"({', '.join(sources)}). "
        f"Average confidence: {label} ({avg_conf:.2f})."
    )


# ── Edge-case detectors ──────────────────────────────────────────────────────

def _detect_conflicts(provenance: list[dict]) -> list[str]:
    """Flag fields that had multiple sources competing (scalar race)."""
    seen_fields: dict[str, set] = {}
    for p in provenance:
        f = p["field"]
        seen_fields.setdefault(f, set()).add(p["source"])
    return [
        f for f, srcs in seen_fields.items()
        if len(srcs) > 1 and p.get("method") != "union"
        for p in provenance if p["field"] == f
    ]


def _multi_source_fields(provenance: list[dict]) -> dict[str, list[str]]:
    """Return {field: [source1, source2, ...]} for fields with >1 source."""
    seen: dict[str, set] = {}
    for p in provenance:
        seen.setdefault(p["field"], set()).add(p["source"])
    return {f: sorted(srcs) for f, srcs in seen.items() if len(srcs) > 1}


def _missing_fields(candidate: dict, expected: list[str]) -> list[str]:
    return [f for f in expected if not candidate.get(f)]


# ── Main reasoning function ──────────────────────────────────────────────────

SCALAR_FIELDS = ["full_name", "headline", "location"]
LIST_FIELDS   = ["emails", "phones", "skills"]
EXPECTED_CORE = ["name", "primary_email"]  # output dict keys, not provenance keys

_DO_NOT_PROCESS_MARKER = "DO_NOT_PROCESS"


def generate_reasoning(candidate: dict) -> dict[str, Any]:
    """
    Accepts one output candidate dict and returns a structured reasoning report.

    Returns
    -------
    dict with keys:
        summary          – one-line verdict
        confidence_band  – HIGH / MEDIUM / LOW
        decisions        – list of narrated field-resolution strings
        conflicts        – list of field names where multiple sources competed
        missing          – list of expected fields that ended up empty / absent
        flags            – list of warning strings (flagged records, sparse data, etc.)
        multi_source     – {field: [source, ...]} for merged fields
    """
    provenance: list[dict] = candidate.get("provenance") or []
    overall    = candidate.get("overall_confidence", 0.0)
    band       = _confidence_label(overall)
    decisions  = []
    flags      = []

    # ── Scalar fields ──────────────────────────────────────────────────────
    for f in SCALAR_FIELDS:
        line = _describe_scalar(f, provenance)
        if line:
            decisions.append(line)

    # ── List fields ────────────────────────────────────────────────────────
    for f in LIST_FIELDS:
        line = _describe_list_field(f, provenance)
        if line:
            decisions.append(line)

    # ── Multi-source conflicts ─────────────────────────────────────────────
    multi = _multi_source_fields(provenance)

    # ── Missing fields ─────────────────────────────────────────────────────
    missing = _missing_fields(candidate, EXPECTED_CORE)
    if missing:
        flags.append(f"Missing expected core fields: {missing}. "
                     "Candidate may be ungroupable or anonymous.")

    # ── Sparse / low confidence ────────────────────────────────────────────
    if overall == 0.0 and not provenance:
        flags.append("No provenance recorded — all sources returned empty or "
                     "unrecognised field names. Check adapter field mapping.")
    elif band == "LOW":
        flags.append(f"Overall confidence is LOW ({overall:.2f}). "
                     "Data is sparse or contradictory across sources.")

    # ── DO NOT PROCESS marker ──────────────────────────────────────────────
    prov_errors = [p for p in provenance if _DO_NOT_PROCESS_MARKER in str(p)]
    if prov_errors or overall == 0.0 and candidate.get("_flagged"):
        flags.append("One or more adapter results were flagged as "
                     "DO NOT PROCESS. Trust weight was zeroed for those sources.")

    # ── Summary ────────────────────────────────────────────────────────────
    name  = candidate.get("name") or "(unknown)"
    email = candidate.get("primary_email") or "(no email)"
    src_count = len({p["source"] for p in provenance})
    summary = (
        f"{name} <{email}> — merged from {src_count} source(s), "
        f"overall confidence: {band} ({overall:.2f})"
    )

    return {
        "summary":         summary,
        "confidence_band": band,
        "decisions":       decisions,
        "conflicts":       list(multi.keys()),
        "multi_source":    multi,
        "missing":         missing,
        "flags":           flags,
    }
