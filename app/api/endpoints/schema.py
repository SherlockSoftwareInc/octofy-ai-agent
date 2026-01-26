from fastapi import APIRouter, HTTPException
from app.models.schemas import TableSchema
from app.services.vector_store import get_vector_store

router = APIRouter()

def _parse_object_name(object_name: str) -> tuple[str, str]:
    cleaned = object_name.strip().replace('[', '').replace(']', '')
    if "." not in cleaned:
        raise ValueError("Object name must be in schema.table format")
    schema_name, table_name = cleaned.split(".", 1)
    schema_name = schema_name.strip()
    table_name = table_name.strip()
    if not schema_name or not table_name:
        raise ValueError("Object name must be in schema.table format")
    return schema_name, table_name

@router.get("/schema/{object_name}", response_model=TableSchema)
def get_schema_by_name(object_name: str):
    try:
        schema_name, table_name = _parse_object_name(object_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    vector_store = get_vector_store()
    schema = vector_store.get_schema_by_name(schema_name, table_name)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Schema not found for {schema_name}.{table_name}")
    return schema
