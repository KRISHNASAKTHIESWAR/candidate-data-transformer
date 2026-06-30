<div align="center">

# 🔄 Candidate Data Transformer

**A fault-tolerant data transformation pipeline for standardizing and merging messy candidate data from PDFs, CSVs, and JSONs.**

*Transforms raw, heterogeneous recruiter data into clean, enriched, audit-ready canonical profiles.*

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python)](https://python.org)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=flat-square)](https://docs.pydantic.dev)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**Author:** E Krishna Shakthi Eswar

</div>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Setup & Installation](#-setup--installation)
- [How to Run](#-how-to-run)
- [Configuration Reference](#-configuration-reference)
- [Feature Deep Dives](#-feature-deep-dives)
- [Output Schema](#-output-schema)
- [Running Tests](#-running-tests)

---

## 🧭 Overview

The Candidate Data Transformer is a production-grade ETL pipeline built to solve a real-world data chaos problem: recruiting teams collect candidate data from a dozen different formats (ATS exports, CSV sheets, PDF resumes, recruiter notes), and none of them agree.

This pipeline ingests all those sources, resolves conflicts mathematically, and emits a single clean, enriched **Canonical Profile** per candidate — complete with a confidence score, a provenance audit trail, and derived career insights.

### What it solves

| Problem | Solution |
|---|---|
| Duplicate candidates across sources | Identity Collision Guard with multi-signal resolution |
| Conflicting field values (e.g., two different job titles) | Confidence-weighted merge engine picks the best value |
| Inconsistent phone / date / skill formats | Normalization layer enforces `E.164`, `YYYY-MM`, and canonical skill names |
| No auditability of data origin | Provenance trail logged for every single field |
| Missing career insights | Derived Feature Engine calculates seniority, tenure, and velocity automatically |

---

## 🏗 Architecture

The pipeline is divided into **4 strict layers**, each with a single responsibility.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        RAW INPUT FILES                                  │
│           .csv          .json          .pdf          .txt               │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — INGESTION (Adapters)                                         │
│                                                                         │
│   CsvAdapter ──┐                                                        │
│  AtsJsonAdapter├──► safe_extract() ──► AdapterResult(raw_fields, trust) │
│    PdfAdapter ─┤                                                        │
│  NotesAdapter ─┘                                                        │
│                                                                         │
│  Each adapter has a trust_weight. Failures are caught and returned      │
│  as empty AdapterResults — the pipeline never crashes on bad files.     │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — NORMALIZATION                                                │
│                                                                         │
│   Field Remapping   →  CSV / ATS / Notes field maps to canonical names  │
│   Date Normalization →  Any date format → YYYY-MM                       │
│   Phone Normalization → Any phone format → E.164 (+1XXXXXXXXXX)         │
│   Skill Canonicalization → "ML", "Machine Learning" → "machine_learning"│
│   Flag Filtering    → "DO NOT PROCESS" records are dropped              │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 3 — GROUPING, MERGING & ENRICHMENT                               │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Identity Resolution (Collision Guard)                           │   │
│  │  Groups records by: candidate_id > email > linkedin > phone+name │   │
│  │  Detects same-name + different-email conflicts → separates them  │   │
│  └──────────────────────────┬───────────────────────────────────────┘   │
│                             │                                           │
│  ┌──────────────────────────▼───────────────────────────────────────┐   │
│  │  MergeEngine                                                     │   │
│  │  Scalar fields → highest confidence_score wins                   │   │
│  │  List fields   → union merge (deduped)                           │   │
│  │  Dict fields   → key-wise best confidence merge                  │   │
│  │  Conflicts logged to conflicts_resolved[]                        │   │
│  │  ProvenanceEntry written for every field                         │   │
│  └──────────────────────────┬───────────────────────────────────────┘   │
│                             │                                           │
│  ┌──────────────────────────▼───────────────────────────────────────┐   │
│  │  Derived Feature Engine (enrich_profile)                         │   │
│  │  • total_years_experience  — calculated from experience[].dates  │   │
│  │  • seniority_level         — Junior / Mid-Level / Senior         │   │
│  │  • average_tenure          — total_years / job_count             │   │
│  │  • career_velocity         — High Mobility/Normal /High Retention│   │
│  │  • executive_summary       — Auto-generated narrative string     │   │
│  └──────────────────────────┬───────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — PROJECTION                                                   │
│                                                                         │
│   config.json defines output shape:                                     │
│   • Rename fields  (e.g., full_name → name)                             │
│   • Drop fields    (e.g., internal_id)                                  │
│   • Index into lists (e.g., emails[0] → primary_email)                  │
│   • Apply transforms (e.g., seniority_level → uppercase)                │
│   • Normalize on output (E164 phone, canonical skill names)             │
│                                                                         │
│                        ► output.json                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
ef-candidate-data-transformers/
│
├── main.py                   # CLI entrypoint & pipeline orchestrator
├── config.json               # Runtime projection configuration
├── requirements.txt          # Python dependencies
│
├── adapters/                 # Layer 1: Ingestion
│   ├── base.py               # BaseAdapter + AdapterResult dataclass
│   ├── csv_adapter.py        # Recruiter CSV files
│   ├── ats_json_adapter.py   # ATS system JSON exports
│   ├── pdf_adapter.py        # PDF resume parsing (pdfplumber)
│   └── notes_adapter.py      # Recruiter plain-text notes
│
├── core/                     # Layers 2, 3 & engine logic
│   ├── normalizer.py         # Date, phone, skill, LinkedIn normalization
│   ├── merger.py             # MergeEngine: conflict resolution + provenance
│   ├── confidence.py         # Confidence score calculation
│   ├── derived.py            # Derived Feature Engine (tenure, seniority, etc.)
│   ├── projector.py          # Layer 4: dynamic output shaping
│   ├── reasoner.py           # Audit reasoning utilities
│   └── alias_map.json        # Skill canonical name mapping table
│
├── models/                   # Pydantic v2 data models
│   ├── canonical.py          # CanonicalProfile + ProvenanceEntry schemas
│   └── config.py             # RuntimeConfig schema
│
├── sample_inputs/            # Example input files for testing
├── sample_input_new/         # Additional test input data
│
└── tests/                    # Test suite
    ├── test_merger.py
    ├── test_normalizers.py
    ├── test_projector.py
    ├── test_mvp_adapters.py
    └── validate_pipeline.py  # End-to-end pipeline validation
```

---

## ⚙️ Setup & Installation

### Prerequisites

- Python **3.11+**
- `pip`

### 1. Clone the Repository

```bash
git clone https://github.com/KRISHNASAKTHIESWAR/candidate-data-transformer.git
cd candidate-data-transformer
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Dependencies overview:**

| Package | Purpose |
|---|---|
| `pydantic>=2.4.2` | Strict schema validation for canonical profiles |
| `phonenumbers>=8.13.22` | International phone number parsing & E.164 normalization |
| `pdfplumber` / `PyPDF2` | PDF resume text extraction |
| `python-dateutil>=2.8.2` | Robust multi-format date parsing |
| `rich>=13.6.0` | CLI output formatting |
| `pytest>=7.4.2` | Test runner |

---

## 🚀 How to Run

### Basic Run

```bash
python main.py --input_dir ./sample_inputs --config config.json --output output.json
```

### Full CLI Reference

```bash
python main.py \
  --input_dir ./data \        # Directory containing raw .csv, .json, .pdf, .txt files
  --config config.json \      # Projection configuration file
  --output output.json \      # Path for the final merged output
  --cli_format summary        # Optional: none | json | summary
```

### CLI Output Modes

| `--cli_format` | Behaviour |
|---|---|
| `none` *(default)* | Silent — only writes to `output.json` |
| `json` | Prints the full JSON output to stdout |
| `summary` | Prints a human-readable executive summary per candidate |

#### Example `summary` output

```
==================================================
CANDIDATE SUMMARIES
==================================================

* Ram Kumar (Velocity: High Retention)
  Senior candidate with 9.2 years of experience, recently at Stripe.
  Specializes in python, machine_learning, data_engineering.

* Ravichandran (Velocity: Normal)
  Mid-Level candidate with 4.5 years of experience, recently at Acme Corp.
```

---

## 🎛 Configuration Reference

The `config.json` file controls how the internal `CanonicalProfile` is **projected** into your final output. It defines a list of field mappings.

### Full Example

```json
{
  "fields": [
    { "path": "candidate_id",   "from_": "candidate_id",          "type": "string",  "required": true  },
    { "path": "name",           "from_": "full_name",             "type": "string",  "required": true  },
    { "path": "primary_email",  "from_": "emails[0]",             "type": "string",  "required": false },
    { "path": "all_emails",     "from_": "emails",                "type": "list",    "required": false },
    { "path": "phone",          "from_": "phones[0]",             "type": "string",  "required": false, "normalize": "E164"       },
    { "path": "city",           "from_": "location.city",         "type": "string",  "required": false },
    { "path": "github",         "from_": "links.github",          "type": "string",  "required": false },
    { "path": "linkedin",       "from_": "links.linkedin",        "type": "string",  "required": false },
    { "path": "skills",         "from_": "skills[].name",         "type": "list",    "required": false, "normalize": "canonical"  },
    { "path": "current_role",   "from_": "experience[0].title",   "type": "string",  "required": false },
    { "path": "seniority",      "from_": "seniority_level",       "type": "string",  "required": false, "transform": "uppercase"  },
    { "path": "years_experience","from_": "total_years_experience","type": "number",  "required": false },
    { "path": "career_velocity","from_": "career_velocity",       "type": "string",  "required": false },
    { "path": "trust_score",    "from_": "overall_confidence",    "type": "number",  "required": false },
    { "path": "executive_summary","from_": "executive_summary",   "type": "string",  "required": false }
  ],
  "include_confidence": true,
  "on_missing": "omit"
}
```

### Field Mapping Options

| Key | Description | Example |
|---|---|---|
| `path` | Output field name in the final JSON | `"name"` |
| `from_` | Source path in the `CanonicalProfile` | `"full_name"`, `"emails[0]"`, `"links.github"` |
| `type` | Expected type (`string`, `number`, `list`) | `"string"` |
| `required` | If `true`, profile is omitted if field is missing | `true` |
| `normalize` | Apply a normalization pass on output | `"E164"`, `"canonical"` |
| `transform` | Apply a string transform on output | `"uppercase"`, `"lowercase"` |

### Global Options

| Key | Values | Description |
|---|---|---|
| `include_confidence` | `true` / `false` | Include `trust_score` in output |
| `on_missing` | `"omit"` / `"null"` | How to handle missing optional fields |

---

## 🔍 Feature Deep Dives

### 🛡 Identity Collision Guard

Prevents "Frankenstein" profiles — records from different candidates who share the same name but are clearly different people (different emails, different companies).

**Resolution priority chain:**

```
candidate_id  →  email  →  linkedin_url  →  phone + name
```

If two records share a **name** but have **conflicting emails**, the guard checks for a secondary confirming signal (LinkedIn URL or phone+name match). If no confirming signal exists, the records are kept as separate profiles and a warning is logged:

```
WARNING: Potential duplicate identity detected for john smith.
         Keeping profiles separate due to conflicting emails.
```

---

### 🧠 Derived Feature Engine

After merging, the `enrich_profile()` function automatically computes:

| Derived Field | Logic |
|---|---|
| `total_years_experience` | Sum of all `(end - start)` durations in `experience[]`, in years |
| `average_tenure` | `total_years / job_count` |
| `seniority_level` | `< 3 yrs` → Junior · `3–7 yrs` → Mid-Level · `> 7 yrs` → Senior |
| `career_velocity` | `avg_tenure < 1.5` → High Mobility · `> 3.5` → High Retention · else Normal |
| `executive_summary` | Auto-generated narrative string summarising the candidate |

All derived fields are added to the **Provenance audit trail** with `source: "derived_engine"`.

---

### 📋 Provenance Audit Trail

Every field in the output has a matching `ProvenanceEntry` documenting exactly where it came from:

```json
{
  "field": "full_name",
  "source": "ats_json",
  "method": "highest_confidence",
  "confidence": 0.88
}
```

| `method` value | Meaning |
|---|---|
| `highest_confidence` | Scalar field — best trust-weighted value won |
| `union` | List field — all unique values collected across sources |
| `merge_keys` | Dict field — best value per key across sources |
| `calculated` | Derived by the Derived Feature Engine |

---

### 🔒 Conflict Resolution Log

When two sources disagree on a scalar field, the conflict is logged in `conflicts_resolved[]`:

```json
{
  "field": "full_name",
  "winning_value": "Jane Doe",
  "losing_value": "J. Doe",
  "winning_source": "ats_json",
  "losing_source": "recruiter_csv"
}
```

---

## 📤 Output Schema

A sample output record looks like this:

```json
{
  "candidate_id": "a3f9...sha256...",
  "name": "Jane Doe",
  "primary_email": "jane.doe@email.com",
  "phone": "+14155550100",
  "city": "San Francisco",
  "linkedin": "https://linkedin.com/in/janedoe",
  "github": "https://github.com/janedoe",
  "skills": ["python", "machine_learning", "data_engineering"],
  "current_role": "Senior Data Engineer",
  "current_company": "Stripe",
  "years_experience": 9.2,
  "seniority": "SENIOR",
  "average_tenure": 3.1,
  "career_velocity": "High Retention",
  "trust_score": 0.86,
  "conflicts_resolved": [
    {
      "field": "full_name",
      "winning_value": "Jane Doe",
      "losing_value": "J. Doe",
      "winning_source": "ats_json",
      "losing_source": "recruiter_csv"
    }
  ],
  "executive_summary": "Senior candidate with 9.2 years of experience, recently at Stripe. Specializes in python, machine_learning, data_engineering."
}
```

---

## 🧪 Running Tests

```bash
# Run all unit tests
pytest tests/

# Run a specific test module
pytest tests/test_merger.py -v

# Run end-to-end pipeline validation
python tests/validate_pipeline.py
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
