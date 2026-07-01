# Candidate Data Transformer: Rule Book

This document serves as the operational manual for executing, configuring, and extending the pipeline.

## 1. Running the Pipeline
The primary entry point is `main.py`.

**Standard Execution:**
```bash
python main.py --input_dir sample_input_new --config config.json --output output.json
```
**Options:**
*   `--input_dir`: Directory containing raw files (CSV, JSON, TXT, PDF).
*   `--cli_format`: Display mode (`none`, `json`, or `summary`).
    *   *Tip:* Use `--cli_format summary` to print a clean list of generated executive summaries to the terminal.

## 2. Using the Audit Report
If you need to understand *why* the pipeline merged a record or dropped a field, run the audit tool:

```bash
python audit_report.py --output output.json
```

**Filters:**
*   `--filter <substring>`: Search by name or email (e.g., `--filter noah`).
*   `--band <HIGH|MEDIUM|LOW>`: Filter by overall confidence tier.
*   `--flags-only`: Show only candidates with warnings (e.g., missing core fields, low confidence).
*   `--summary-only`: Print only the aggregate statistics and table without the detailed narrative panels.

## 3. Configuration & Field Mapping
The pipeline output is strictly controlled by `config.json`. To modify the output shape, edit `config.json` rather than the core code.

```json
{
  "fields": [
    {
      "path": "name",           // The field name in the output JSON
      "from": "full_name",      // The field name in the CanonicalProfile
      "type": "string",
      "required": true
    }
  ],
  "include_confidence": true,   // If true, outputs provenance/confidence metadata
  "on_missing": "omit"          // 'omit', 'null', or 'error' behavior for missing fields
}
```

## 4. Exclusion & "DO NOT PROCESS"
*   If a recruiter note or input explicitly contains phrases like `"do not process"`, `"do not send"`, or `"flag and exclude"`, the pipeline will immediately zero out the trust weight for that specific source.
*   The `audit_report.py` will explicitly flag these candidates in the terminal output.

## 5. Adding New Data Sources (Adapters)
To add a new file format or data source:
1. Create a new file in `adapters/` (e.g., `xml_adapter.py`).
2. Create a class inheriting from `BaseAdapter`.
3. Set the `source_name` and a hardcoded `trust_weight` (0.0 to 1.0) in the `__init__`.
    *   *Rule of thumb:* Structured internal APIs -> High (0.9); Parsing external resumes/notes -> Medium-Low (0.4 - 0.7).
4. Implement the `extract(self, source)` method to parse the file and return a raw dictionary.
5. Register the adapter in `main.py` and map its raw fields to the `CanonicalProfile` fields using a new `FIELD_MAP`.

## 6. Edge Cases & Collision Guard
*   **Duplicate Names, Different Emails:** If two profiles share a name but have different emails, the system defaults to keeping them separate. It will only merge them if there is a secondary corroborating match (like identical LinkedIn URLs or phone numbers).
*   **Sparse Records:** Candidates missing expected core fields (like `name` or `primary_email`) will be compiled but heavily flagged in the audit report.
