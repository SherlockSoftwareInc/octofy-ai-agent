from pathlib import Path
from typing import Optional, Tuple

from app.models.schemas import TableSchema
from app.services.vector_store import get_vector_store


LIST_PATH = Path(__file__).resolve().parent / "NorthwindSchemas.txt"

VIEW_NAMES = {
    "Alphabetical list of products",
    "Category Sales for 1997",
    "Current Product List",
    "Customer and Suppliers by City",
    "Invoices",
    "Order Details Extended",
    "Order Subtotals",
    "Orders Qry",
    "Product Sales for 1997",
    "Products Above Average Price",
    "Products by Category",
    "Quarterly Orders",
    "Sales by Category",
    "Sales Totals by Amount",
    "Summary of Sales by Quarter",
    "Summary of Sales by Year",
}


def _normalize_brackets(raw_name: str) -> Tuple[str, str]:
    name = raw_name.strip()
    if not name:
        return "", ""

    if name.startswith("[") and name.endswith("["):
        name = f"{name[:-1]}]"
    elif name.startswith("[") and not name.endswith("]"):
        name = f"{name}]"

    unbracketed = name
    if unbracketed.startswith("[") and unbracketed.endswith("]"):
        unbracketed = unbracketed[1:-1]

    return unbracketed, name


def _parse_object_line(line: str) -> Optional[Tuple[str, str, str]]:
    raw = line.strip()
    if not raw:
        return None

    if "." in raw:
        raw_schema, raw_table = raw.split(".", 1)
    else:
        raw_schema, raw_table = "dbo", raw

    schema = raw_schema.strip()
    if schema.startswith("[") and schema.endswith("]"):
        schema = schema[1:-1]

    table_name, table_display = _normalize_brackets(raw_table)
    if not table_name:
        return None

    return schema, table_name, table_display


def _resolve_table_type(table_name: str) -> str:
    return "view" if table_name.lower() in {n.lower() for n in VIEW_NAMES} else "table"


def _build_stub_description(schema_name: str, table_name: str, table_type: str) -> str:
    type_label = "View" if table_type == "view" else "Table"
    return (
        f"# **{type_label}:** `[{schema_name}].[{table_name}]`\n"
        f"> Auto-synced stub from NorthwindSchemas.txt (no column metadata).\n"
        "---\n"
    )


def sync_schema_index() -> None:
    if not LIST_PATH.exists():
        raise FileNotFoundError(f"Could not find list at {LIST_PATH}")

    store = get_vector_store()
    lines = LIST_PATH.read_text(encoding="utf-8").splitlines()
    total = 0

    for line in lines:
        parsed = _parse_object_line(line)
        if not parsed:
            continue

        schema_name, table_name, _table_display = parsed
        table_type = _resolve_table_type(table_name)
        description = _build_stub_description(schema_name, table_name, table_type)

        schema = TableSchema(
            schema_name=schema_name,
            table_name=table_name,
            table_type=table_type,
            description=description,
            columns=[],
        )

        try:
            store.insert_schema_embedding(schema, description, table_type=table_type)
            print(f"Synced {schema_name}.{table_name} ({table_type})")
            total += 1
        except Exception as exc:
            print(f"Failed to sync {schema_name}.{table_name}: {exc}")

    print(f"Done. Synced {total} objects.")


if __name__ == "__main__":
    sync_schema_index()
