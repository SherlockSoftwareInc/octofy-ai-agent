from fastapi import APIRouter, HTTPException, Depends
from app.core.auth import get_current_active_admin
from app.models.pipeline import SemanticModel, SmqPayload
from app.models.user_models import User
from app.services.source_resolver import resolve_known_source_id
from app.services.stores.bundle import build_source_stores
from app.services.semantic_compiler import SemanticCompilationError, SemanticCompiler
from app.services.semantic_extraction_service import SemanticModelExtractionService
from typing import Optional

router = APIRouter()


@router.get("/semantic-models")
def list_models(source_id: str, current_user: User = Depends(get_current_active_admin)):
    source_id = resolve_known_source_id(source_id)
    stores = build_source_stores(source_id)
    return {"models": [m.model_dump() for m in stores.semantic.list_models()]}


@router.post("/semantic-models")
def save_model(source_id: str, model: SemanticModel, current_user: User = Depends(get_current_active_admin)):
    source_id = resolve_known_source_id(source_id)
    stores = build_source_stores(source_id)
    saved = stores.semantic.save(model)
    return saved.model_dump()


@router.post("/semantic-models/extract")
def extract_model(source_id: str, payload: dict, current_user: User = Depends(get_current_active_admin)):
    source_id = resolve_known_source_id(source_id)
    extractor = SemanticModelExtractionService()
    model = extractor.extract(
        schema_text=payload.get("schema_text") or "",
        sql=payload.get("sql"),
        label=payload.get("label") or "Model",
    )
    stores = build_source_stores(source_id)
    saved = stores.semantic.save(model)
    return saved.model_dump()


@router.post("/semantic-models/compile")
def compile_smq(source_id: str, payload: dict, current_user: User = Depends(get_current_active_admin)):
    source_id = resolve_known_source_id(source_id)
    stores = build_source_stores(source_id)
    model = stores.semantic.get_active_model()
    if not model:
        raise HTTPException(status_code=404, detail="No active semantic model")
    try:
        smq = SmqPayload.model_validate(payload.get("smq") or payload)
        sql = SemanticCompiler().compile(smq, model, payload.get("dbms") or "SQL Server")
        return {"sql": sql}
    except SemanticCompilationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
