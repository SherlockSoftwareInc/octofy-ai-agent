"""Wipe and rebuild Northwind vector collections from the skills folder."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE_ID = "1b2b4f87-5ef6-4389-976e-cee2ff56464f"
FOLDER = ROOT / "skills" / "data-sources" / "northwind"
VALUE_CSV = ROOT / "northwind_value_sets.csv"

from app.models.schemas import ColumnInfo, DataObject, ObjectType, TableSchema
from app.services.stores.milvus_provider import MilvusProvider
from app.services.stores.milvus_replicate import replicate_sqlite_to_milvus
from app.services.stores.provider_factory import get_vector_provider
from app.services.stores.schema_contracts import COLLECTIONS
from app.services.stores.skills_folder import _parse_columns, _parse_object_file, rebuild_vectors_from_folder
from app.services.stores.sqlite_vec_provider import SqliteVecProvider
from app.services.value_index_service import ValueIndexService
from app.services.vector_store import get_vector_store


def _wipe_all(provider, source_id: str) -> None:
    names = [spec.name for spec in COLLECTIONS]
    for name in names:
        try:
            provider.delete_source(name, source_id)
            print(f"  wiped {name}", flush=True)
        except Exception as exc:
            print(f"  skip wipe {name}: {exc}", flush=True)


def _ingest_legacy_from_markdown() -> tuple[int, int]:
    vs = get_vector_store()
    vs.clear_schemas_collection(SOURCE_ID)
    if hasattr(vs, "clear_source_objects_v2"):
        vs.clear_source_objects_v2(SOURCE_ID)
    if hasattr(vs, "clear_values_collection"):
        vs.clear_values_collection(SOURCE_ID)

    schemas_dir = FOLDER / "schemas"
    schema_count = 0
    v2_count = 0
    type_map = {
        "Table": ObjectType.TABLE,
        "View": ObjectType.VIEW,
        "Function": ObjectType.FUNCTION,
    }
    for md in sorted(schemas_dir.rglob("*.md")):
        text = md.read_text(encoding="utf-8", errors="ignore")
        schema_name, object_name, object_type = _parse_object_file(md)
        table_type = "view" if object_type.lower() == "view" else "table"
        columns = [
            ColumnInfo(name=n, data_type=t, description=d)
            for n, t, d in _parse_columns(text)
        ]
        schema = TableSchema(
            schema_name=schema_name,
            table_name=object_name,
            table_type=table_type,
            description=text[:4000],
            columns=columns,
            source_guid=SOURCE_ID,
        )
        vs.insert_schema_embedding(schema, text[:4000], table_type=table_type)
        schema_count += 1
        obj = DataObject(
            source_id=SOURCE_ID,
            schema_name=schema_name,
            object_name=object_name,
            object_type=type_map.get(object_type, ObjectType.TABLE),
            description=text[:4000],
            columns=columns,
        )
        vs.insert_data_object_v2(obj, text[:4000])
        v2_count += 1
        print(f"  legacy {schema_name}.{object_name}")
    return schema_count, v2_count


def _read_value_rows(path: Path) -> list[dict]:
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin1", "utf-16"]
    last_err = None
    for enc in encodings:
        try:
            with path.open(encoding=enc, newline="") as fh:
                reader = csv.DictReader(fh)
                rows = []
                for raw in reader:
                    value = (raw.get("value") or "").strip()
                    if not value:
                        continue
                    rows.append({
                        "value": value,
                        "schema_name": (raw.get("schema_name") or "dbo").strip(),
                        "table_name": (raw.get("table_name") or "").strip(),
                        "column_name": (raw.get("column_name") or "").strip(),
                    })
                return rows
        except UnicodeDecodeError as exc:
            last_err = exc
            continue
    raise RuntimeError(f"Unable to read {path}: {last_err}")


def _load_values(providers) -> int:
    if not VALUE_CSV.exists():
        print("No northwind_value_sets.csv; skipping value index", flush=True)
        return 0
    rows = _read_value_rows(VALUE_CSV)
    seen = set()
    unique = []
    for row in rows:
        key = (row["value"], row["schema_name"], row["table_name"], row["column_name"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)

    sqlite = SqliteVecProvider()
    values = ValueIndexService(sqlite, SOURCE_ID)
    values.clear()
    for i, row in enumerate(unique, 1):
        values.upsert(
            value=row["value"],
            schema_name=row["schema_name"],
            table_name=row["table_name"],
            column_name=row["column_name"],
        )
        if i % 25 == 0 or i == len(unique):
            print(f"  sqlite values {i}/{len(unique)}", flush=True)

    for provider in providers:
        if provider is sqlite:
            continue
        try:
            rows = sqlite.fetch_all("value_index", SOURCE_ID)
            converted = []
            for row in rows:
                rec = dict(row)
                rec["vector"] = loads_vector(rec.get("vector")) if not isinstance(rec.get("vector"), list) else rec["vector"]
                converted.append(rec)
            provider.delete_source("value_index", SOURCE_ID)
            if converted:
                provider.upsert("value_index", converted)
            print(f"  copied {len(converted)} values to provider", flush=True)
        except Exception as exc:
            print(f"  provider value copy skipped: {exc}", flush=True)
    try:
        vs = get_vector_store()
        vs.clear_values_collection(SOURCE_ID)
        vs.insert_value_items_batch(unique, source_guid=SOURCE_ID)
    except Exception as exc:
        print(f"  legacy value ingest skipped: {exc}")
    return len(unique)


def main() -> int:
    if not FOLDER.exists():
        print(f"ERROR: Northwind folder not found: {FOLDER}")
        return 1

    print(f"Rebuilding Northwind from {FOLDER}", flush=True)
    print(f"source_id={SOURCE_ID}", flush=True)

    sqlite = SqliteVecProvider()

    print("\n[1/4] Wipe sqlite_vec collections", flush=True)
    _wipe_all(sqlite, SOURCE_ID)

    print("\n[2/4] Rebuild schemas, data groups, and precomputed QAs", flush=True)
    report = rebuild_vectors_from_folder(FOLDER, SOURCE_ID, sqlite)
    print(
        f"  objects={report.objects} groups={report.groups} qas={report.qas} "
        f"errors={len(report.errors)}",
        flush=True,
    )
    for err in report.errors[:20]:
        print(f"  error: {err}", flush=True)

    configured = None
    try:
        configured = get_vector_provider()
    except Exception as exc:
        print(f"configured provider unavailable: {exc}", flush=True)

    try:
        milvus = MilvusProvider()
        if getattr(milvus, "_connected", False):
            print("\n[2b] Drop Milvus collections and replicate all SQLite tables", flush=True)
            dropped = milvus.drop_all_collections()
            print(f"  dropped {len(dropped)} collections", flush=True)
            counts = replicate_sqlite_to_milvus(sqlite, milvus)
            for name, count in counts.items():
                if count:
                    print(f"  {name}={count}", flush=True)
            print(f"  mirrored {sum(counts.values())} rows", flush=True)
        else:
            print("\n[2b] Milvus not connected; skipped replica", flush=True)
    except Exception as exc:
        print(f"  milvus replicate failed: {exc}", flush=True)

    print("\n[3/4] Rebuild legacy Milvus schema_index / schema_index_v2", flush=True)
    try:
        n1, n2 = _ingest_legacy_from_markdown()
        print(f"  schema_index={n1} schema_index_v2={n2}", flush=True)
    except Exception as exc:
        print(f"  legacy ingest failed: {exc}", flush=True)

    print("\n[4/4] Load value index", flush=True)
    providers = [sqlite]
    if configured is not None and configured is not sqlite:
        providers.append(configured)
    count = _load_values(providers)
    print(f"  values={count}", flush=True)

    print("\nDone.", flush=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--values-only":
        sqlite = SqliteVecProvider()
        providers = [sqlite]
        try:
            configured = get_vector_provider()
            if configured is not None and configured is not sqlite:
                providers.append(configured)
        except Exception as exc:
            print(f"configured provider unavailable: {exc}", flush=True)
        count = _load_values(providers)
        print(f"  values={count}", flush=True)
        print("Done.", flush=True)
        raise SystemExit(0)
    raise SystemExit(main())
