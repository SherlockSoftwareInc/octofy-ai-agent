import argparse
import os
import json
from typing import Optional
from app.services.admin_service import ingest_values_from_excel
from app.services.vector_store import get_vector_store
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Load a CSV/XLSX into the Value Index collection")
    parser.add_argument("path", help="Path to the CSV or XLSX file")
    parser.add_argument("--mode", choices=["append", "replace"], default="append", help="Append or replace existing values")
    args = parser.parse_args()

    file_path = args.path
    if not os.path.exists(file_path):
        print(f"ERROR: File not found: {file_path}")
        raise SystemExit(1)

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        # Handle CSV locally to support non-UTF8 encodings
        encodings_to_try = ["utf-8", "utf-8-sig", "cp1252", "latin1", "utf-16", "utf-16-le", "utf-16-be"]
        df = None
        last_err: Optional[Exception] = None
        for enc in encodings_to_try:
            try:
                df = pd.read_csv(file_path, encoding=enc)
                break
            except Exception as e:
                last_err = e
                continue
        if df is None:
            print(f"ERROR: Unable to read CSV with tried encodings. Last error: {last_err}")
            raise SystemExit(2)

        # Normalize columns
        df.columns = df.columns.str.strip().str.lower()
        required_cols = ['value', 'schema_name', 'table_name', 'column_name']
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            print(f"ERROR: Missing required columns: {', '.join(missing_cols)}. Found: {', '.join(df.columns)}")
            raise SystemExit(3)

        df = df[required_cols + [c for c in df.columns if c not in required_cols]].copy()
        df['value'] = df['value'].astype(str).str.strip()
        df = df.drop_duplicates(subset=['value', 'schema_name', 'table_name', 'column_name'])
        df = df[df['value'].notna() & (df['value'] != '')]
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
                if 'metadata' in df.columns:
                    try:
                        meta_val = row.get('metadata', '{}')
                        if isinstance(meta_val, str) and meta_val:
                            metadata = json.loads(meta_val)
                    except Exception:
                        metadata = {}
                vs.insert_value_item(
                    value=str(row['value']),
                    schema_name=str(row['schema_name']),
                    table_name=str(row['table_name']),
                    column_name=str(row['column_name']),
                    metadata=metadata,
                )
                success += 1
            except Exception as e:
                print(f"WARN: Failed to insert value '{row.get('value')}' -> {e}")
                continue
        print(f"Status: success\nMessage: Successfully ingested {success} values\nRows processed: {success}/{len(df)}")
    else:
        # Delegate to admin service for xlsx
        with open(file_path, "rb") as f:
            content = f.read()
        result = ingest_values_from_excel(content, mode=args.mode, file_type="xlsx")
        status = result.get("status")
        message = result.get("message")
        rows = result.get("rows_processed", 0)
        total = result.get("total_rows", rows)
        print(f"Status: {status}\nMessage: {message}\nRows processed: {rows}/{total}")


if __name__ == "__main__":
    main()
