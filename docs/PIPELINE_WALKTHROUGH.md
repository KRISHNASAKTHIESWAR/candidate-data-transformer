# Pipeline Walkthrough

This document outlines the internal architecture and data flow of the Candidate Data Transformer pipeline. The system is designed to ingest heterogeneous candidate profiles from multiple sources, normalize the data, intelligently merge duplicates, derive insights, and project the final canonical profiles into a specified output schema.

## 1. Ingestion Layer (Adapters)
The pipeline begins by reading files from the input directory (default: `sample_input_new/`). Files are routed to the appropriate `Adapter` based on their extension.

*   **CsvAdapter (.csv):** Parses tabular recruiter exports.
*   **AtsJsonAdapter (.json):** Parses structured outputs from Applicant Tracking Systems.
*   **NotesAdapter (.txt):** Uses regex heuristics to extract entities (emails, links, experience, degrees) from unstructured recruiter notes.
*   **PdfAdapter (.pdf):** Uses `pdfplumber` to extract text from resumes and identifies emails, phone numbers, and names via regex heuristics.

Each adapter implements `BaseAdapter`, assigning a `trust_weight` (0.0 to 1.0) and returning an `AdapterResult`.

## 2. Normalization
Before profiles are merged, raw fields are normalized to prevent duplicate/messy data:
*   **Phones:** Parsed via `phonenumbers` to standardized E.164 format.
*   **Dates:** Parsed via `dateutil` to `YYYY-MM` format.
*   **Skills:** Standardized using the `SKILL_ALIASES` mapping (e.g., mapping "Node" -> "Node.js").
*   **URLs:** Query parameters are stripped, and handles are extracted to create clean URLs.

## 3. Entity Resolution & Grouping
The pipeline explodes the parsed data into individual records and groups them using deterministic hashing. 

*   **Keys Used:** Records are grouped if they share a common identifier (Application ID, Email, LinkedIn URL, or Phone + Name).
*   **Collision Guard:** If an entity shares a Name but has conflicting Emails, the system checks for a multi-signal override (e.g., shared LinkedIn). If no strong link exists, it spawns a separate profile to prevent a "Frankenstein" merge.

## 4. The Merge Engine
Grouped profiles are passed to the `MergeEngine` which synthesizes a single `CanonicalProfile`.

*   **List Union:** Fields like `emails`, `phones`, and `skills` are combined into deduplicated lists.
*   **Scalar Overrides:** Singular fields (like `full_name` or `location`) are selected using a "winner-takes-all" approach based on the highest `trust_weight` (confidence score).
*   **Provenance:** Every decision is recorded as a `ProvenanceEntry`, explicitly stating which source provided the data, the method used ("override", "union"), and the confidence score.

## 5. Derived Feature Engine
After merging, `core.derived` enriches the candidate profile with calculated insights:
*   **Experience Metrics:** Calculates total years of experience by summing job durations.
*   **Career Velocity:** Flags candidates as "High Mobility", "Normal", or "High Retention" based on average tenure per role.
*   **Seniority:** Infers level (Junior, Mid-Level, Senior) based on total years of experience.
*   **Executive Summary:** Automatically generates a one-line summary incorporating seniority, tenure, recent company, and top skills.

## 6. Projection Layer
The rich `CanonicalProfile` is passed through the `Projector` which applies the logic defined in `config.json`.
*   **Mapping:** Renames canonical fields to the user's desired output format.
*   **Filtering:** Omit or error-out on missing fields based on the `on_missing` strategy.
*   **Formatting:** Drops internal pipeline fields if not explicitly requested in the configuration.

## 7. Audit & Reporting
The pipeline supports generating deep traceability reports. Using `audit_report.py`, users can view a human-readable narrative (powered by `core.reasoner`) explaining exactly why the engine chose specific data points, highlighting conflicts, and raising flags for low-confidence or manually excluded ("DO NOT PROCESS") records.
