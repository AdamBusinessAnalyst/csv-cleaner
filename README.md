# Excel / CSV Cleaner — powered by Claude AI

Point it at a messy CSV or Excel file: it profiles the data, asks Claude for a cleaning plan as structured JSON (validated with Pydantic), applies the steps it can automate, and saves a cleaned copy.

## What it does

1. Loads your CSV or Excel file
2. Profiles the data (nulls, types, duplicates, samples)
3. Asks Claude to identify issues and plan cleaning steps
4. Applies the cleaning steps automatically
5. Saves a `cleaned_<filename>` output

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Usage

```bash
python3 cleaner.py data.csv
python3 cleaner.py report.xlsx
python3 cleaner.py data.csv --out final_clean.csv
```

## Example output

Illustrative run on a sample sales export:

```
Loading sales_data.csv...
  1200 rows, 8 columns

Asking Claude to analyze data quality...

── Issues found: ──
  • Column 'Email' has 47 null values
  • Column 'Name' has leading/trailing whitespace
  • 23 duplicate rows detected
  • Column 'Revenue' has mixed numeric and string values

── Applying cleaning steps: ──
  Dropped 23 duplicate rows
  Stripped whitespace: 'Name'
  Dropped 47 rows where 'Email' is null
  Filled nulls with median (4250.00): 'Revenue'

Saved cleaned file: cleaned_sales_data.csv
  Before: 1200 rows → After: 1130 rows
```

## Cleaning actions supported

| Issue | Auto-fixed |
|---|---|
| Duplicate rows | Yes |
| Whitespace in strings | Yes |
| Inconsistent casing | Yes |
| Null values (numeric) | Yes — fills with median/mean |
| Null values (required cols) | Yes — drops rows |
| Date format conversion | Yes |

Actions Claude suggests that need manual review are flagged as `[skipped — manual action needed]` so nothing is silently lost.

## Tests

```bash
pytest -q
```

Tests run offline: the Claude call is mocked, so no API key is needed. CI runs flake8 and pytest on Python 3.9, 3.11 and 3.12.

## Where this is useful

Exported data from CRMs, POS systems and spreadsheets that needs a fast first-pass clean before analysis. The model is set in `MODEL` at the top of `cleaner.py`.
