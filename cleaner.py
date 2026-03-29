#!/usr/bin/env python3
"""
Excel/CSV Cleaner powered by Claude
Analyzes your file, identifies data quality issues, and outputs a cleaned version.

Usage:
    python3 cleaner.py data.csv
    python3 cleaner.py report.xlsx
    python3 cleaner.py data.csv --out cleaned.csv
"""

import argparse
import sys
from pathlib import Path

import anthropic
import pandas as pd
from pydantic import BaseModel

# ── Models ────────────────────────────────────────────────────────────────────


class CleaningPlan(BaseModel):
    issues_found: list[str]
    actions_taken: list[str]


# ── Analysis ──────────────────────────────────────────────────────────────────


def build_profile(df: pd.DataFrame) -> str:
    lines = [
        f"Rows: {len(df)}",
        f"Columns: {list(df.columns)}",
        "",
        "Column types and null counts:",
    ]
    for col in df.columns:
        null_count = df[col].isna().sum()
        dtype = str(df[col].dtype)
        sample = df[col].dropna().head(3).tolist()
        lines.append(f"  {col!r}: {dtype}, {null_count} nulls, sample={sample}")

    dupe_count = df.duplicated().sum()
    lines.append(f"\nDuplicate rows: {dupe_count}")

    return "\n".join(lines)


def ask_claude_for_cleaning_plan(profile: str, sample_csv: str) -> CleaningPlan:
    client = anthropic.Anthropic()

    prompt = f"""You are a data analyst. Analyze this dataset profile and sample, then return a JSON cleaning plan.

PROFILE:
{profile}

SAMPLE (first 5 rows as CSV):
{sample_csv}

Return ONLY valid JSON in this exact format:
{{
  "issues_found": ["list of data quality issues you see"],
  "actions_taken": ["list of cleaning steps to apply, be specific about column names and what to do"]
}}

Keep actions concrete and automatable. Examples:
- "Strip whitespace from column 'Name'"
- "Convert column 'Date' to datetime format"
- "Drop duplicate rows"
- "Fill nulls in 'Salary' with column median"
- "Standardize column 'Status' values to lowercase"
- "Remove rows where 'Email' is null"
"""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    import json
    raw = resp.content[0].text.strip()
    # Strip markdown code block if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw.strip())
    return CleaningPlan(**data)


# ── Cleaning ──────────────────────────────────────────────────────────────────


def apply_cleaning(df: pd.DataFrame, plan: CleaningPlan) -> pd.DataFrame:
    df = df.copy()

    for action in plan.actions_taken:
        a = action.lower()

        # Drop duplicates
        if "duplicate" in a:
            before = len(df)
            df = df.drop_duplicates()
            print(f"  Dropped {before - len(df)} duplicate rows")

        # Strip whitespace
        elif "strip whitespace" in a or "whitespace" in a:
            col = _extract_column(action, df.columns)
            if col:
                df[col] = df[col].astype(str).str.strip()
                print(f"  Stripped whitespace: {col!r}")

        # Lowercase
        elif "lowercase" in a or "lower" in a:
            col = _extract_column(action, df.columns)
            if col:
                df[col] = df[col].astype(str).str.lower().str.strip()
                print(f"  Lowercased: {col!r}")

        # Convert to datetime
        elif "datetime" in a or "date" in a and "convert" in a:
            col = _extract_column(action, df.columns)
            if col:
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                    print(f"  Converted to datetime: {col!r}")
                except Exception as e:
                    print(f"  [!] Could not convert {col!r} to datetime: {e}")

        # Fill nulls with median
        elif "median" in a:
            col = _extract_column(action, df.columns)
            if col and pd.api.types.is_numeric_dtype(df[col]):
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                print(f"  Filled nulls with median ({median_val:.2f}): {col!r}")

        # Fill nulls with mean
        elif "mean" in a:
            col = _extract_column(action, df.columns)
            if col and pd.api.types.is_numeric_dtype(df[col]):
                mean_val = df[col].mean()
                df[col] = df[col].fillna(mean_val)
                print(f"  Filled nulls with mean ({mean_val:.2f}): {col!r}")

        # Drop rows where column is null
        elif "remove rows" in a or "drop rows" in a:
            col = _extract_column(action, df.columns)
            if col:
                before = len(df)
                df = df.dropna(subset=[col])
                print(f"  Dropped {before - len(df)} rows where {col!r} is null")

        # Fill nulls with empty string
        elif "fill null" in a or "fillna" in a:
            col = _extract_column(action, df.columns)
            if col:
                df[col] = df[col].fillna("")
                print(f"  Filled nulls with empty string: {col!r}")

        else:
            print(f"  [skipped — manual action needed]: {action}")

    return df


def _extract_column(action: str, columns: list[str]) -> str | None:
    for col in columns:
        if col.lower() in action.lower() or f"'{col}'" in action or f'"{col}"' in action:
            return col
    return None


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Path to CSV or Excel file")
    parser.add_argument("--out", help="Output file path (default: cleaned_<input>)")
    args = parser.parse_args()

    input_path = Path(args.file)
    if not input_path.exists():
        print(f"[!] File not found: {input_path}")
        sys.exit(1)

    # Load
    print(f"\nLoading {input_path.name}...")
    if input_path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(input_path)
    else:
        df = pd.read_csv(input_path)
    print(f"  {len(df)} rows, {len(df.columns)} columns")

    # Profile
    profile = build_profile(df)
    sample_csv = df.head(5).to_csv(index=False)

    # Claude analysis
    print("\nAsking Claude to analyze data quality...")
    plan = ask_claude_for_cleaning_plan(profile, sample_csv)

    print("\n── Issues found: ──")
    for issue in plan.issues_found:
        print(f"  • {issue}")

    print("\n── Applying cleaning steps: ──")
    cleaned_df = apply_cleaning(df, plan)

    # Output
    if args.out:
        out_path = Path(args.out)
    else:
        out_path = input_path.parent / f"cleaned_{input_path.name}"
        if out_path.suffix.lower() in {".xlsx", ".xls"}:
            out_path = out_path.with_suffix(".xlsx")

    if out_path.suffix.lower() in {".xlsx", ".xls"}:
        cleaned_df.to_excel(out_path, index=False)
    else:
        cleaned_df.to_csv(out_path, index=False)

    print(f"\nSaved cleaned file: {out_path}")
    print(f"  Before: {len(df)} rows → After: {len(cleaned_df)} rows")


if __name__ == "__main__":
    main()
