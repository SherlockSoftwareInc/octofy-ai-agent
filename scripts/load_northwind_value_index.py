import argparse
import json
import os
import sys
from pathlib import Path
# Ensure project root is in sys.path for app imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from typing import Optional

import pandas as pd

from app.services.vector_store import get_vector_store


def _default_csv_path() -> str:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(repo_root, "northwind_value_sets.csv")


def _read_csv_with_fallbacks(path: str) -> pd.DataFrame:
    encodings_to_try = [
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin1",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
    ]
    df: Optional[pd.DataFrame] = None
    last_err: Optional[Exception] = None
    for enc in encodings_to_try:
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except Exception as exc:
            last_err = exc
            continue
    if df is None:
        raise RuntimeError(f"Unable to read CSV with tried encodings. Last error: {last_err}")
    return df


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip().str.lower()
    required_cols = ["value", "schema_name", "table_name", "column_name"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        found_cols = ", ".join(df.columns)
        missing = ", ".join(missing_cols)
        raise ValueError(f"Missing required columns: {missing}. Found: {found_cols}")

    df = df[required_cols + [c for c in df.columns if c not in required_cols]].copy()
    df["value"] = df["value"].astype(str).str.strip()
    df = df.drop_duplicates(subset=["value", "schema_name", "table_name", "column_name"])
    df = df[df["value"].notna() & (df["value"] != "")]
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load Northwind value set CSV into the Value Index collection."
    )
    parser.add_argument(
        "--path",
        default=_default_csv_path(),
        help="Path to northwind_value_sets.csv (defaults to repo root file).",
    )
    parser.add_argument(
        "--mode",
        choices=["append", "replace"],
        default="append",
        help="Append or replace existing values.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"ERROR: File not found: {args.path}")
        raise SystemExit(1)

    try:
        df = _read_csv_with_fallbacks(args.path)
        df = _normalize_df(df)
    except Exception as exc:
        print(f"ERROR: Failed to load CSV: {exc}")
        raise SystemExit(2)

    if df.empty:
        print("No valid rows to ingest after cleaning.")
        raise SystemExit(0)

    vs = get_vector_store()
    if args.mode == "replace":
        vs.clear_values_collection()

    success = 0
    for _, row in df.iterrows():
        try:
            metadata = {}
            if "metadata" in df.columns:
                meta_val = row.get("metadata", "{}")
                if isinstance(meta_val, str) and meta_val:
                    try:
                        metadata = json.loads(meta_val)
                    except Exception:
                        metadata = {}
            vs.insert_value_item(
                value=str(row["value"]),
                schema_name=str(row["schema_name"]),
                table_name=str(row["table_name"]),
                column_name=str(row["column_name"]),
                metadata=metadata,
            )
            success += 1
        except Exception as exc:
            print(f"WARN: Failed to insert value '{row.get('value')}' -> {exc}")
            continue

    print(
        "Status: success\n"
        f"Message: Successfully ingested {success} values\n"
        f"Rows processed: {success}/{len(df)}"
    )


if __name__ == "__main__":
    main()
