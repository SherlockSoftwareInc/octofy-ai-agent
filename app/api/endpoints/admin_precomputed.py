from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel

from app.core.auth import get_current_active_admin
from app.models.user_models import User
from app.services.source_resolver import resolve_known_source_id
from app.services.stores.bundle import build_source_stores

router = APIRouter()


class PrecomputedItem(BaseModel):
    question: str
    sql_query: str
    group_name: str
    group_file_name: str = ""
    smq_query: str = ""
    status: str = "Pending"
    query_id: Optional[str] = None


@router.get("/precomputed-queries")
def list_precomputed(source_id: str, status: Optional[str] = None, current_user: User = Depends(get_current_active_admin)):
    source_id = resolve_known_source_id(source_id)
    stores = build_source_stores(source_id)
    return {"items": stores.precomputed.list(status)}


@router.post("/precomputed-queries")
def add_precomputed(source_id: str, item: PrecomputedItem, current_user: User = Depends(get_current_active_admin)):
    source_id = resolve_known_source_id(source_id)
    stores = build_source_stores(source_id)
    query_id = stores.precomputed.upsert(
        question=item.question,
        sql_query=item.sql_query,
        group_name=item.group_name,
        group_file_name=item.group_file_name,
        smq_query=item.smq_query,
        status=item.status,
        query_id=item.query_id,
    )
    return {"query_id": query_id}


@router.post("/precomputed-queries/{query_id}/status")
def set_status(source_id: str, query_id: str, status: str, current_user: User = Depends(get_current_active_admin)):
    source_id = resolve_known_source_id(source_id)
    stores = build_source_stores(source_id)
    stores.precomputed.set_status(query_id, status)
    return {"status": "success"}
