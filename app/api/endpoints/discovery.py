from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import DiscoveryRequest, DiscoveryResponse
from app.services.discovery_service import perform_discovery
from app.core.auth import verify_api_key
from app.core.config import settings

router = APIRouter()

@router.post("/discovery")
def discovery_endpoint(request: dict, api_key: str = Depends(verify_api_key)):
    try:
        from app.models.schemas import DiscoveryRequest, ColumnInfo, TableSchema
        from app.services.source_resolver import require_source_id

        discovery_req = DiscoveryRequest(
            query=request.get("query", ""),
            top_k=request.get("top_k", 5),
            source_id=request.get("source_id"),
        )
        discovery_req.source_id = require_source_id(discovery_req.source_id)
        if getattr(settings, "BUILTIN_SQL_GENERATOR", True):
            from app.core.orchestrator.builtin_sql_generator import discover_for_api
            from app.services.stores.bundle import build_source_stores

            source_id = discovery_req.source_id
            stores = build_source_stores(source_id)
            discovered = discover_for_api(discovery_req.query, stores, top_k=discovery_req.top_k)
            tables = []
            for obj in discovered.objects:
                tables.append({
                    "schema_name": obj.schema_name,
                    "table_name": obj.object_name,
                    "description": obj.description,
                    "similarity_score": obj.score,
                    "matched_columns": obj.matched_columns,
                    "columns": [{"name": c, "data_type": "", "description": None} for c in obj.matched_columns],
                })
            return {
                "query": discovery_req.query,
                "reasoning": discovered.branch,
                "context": {
                    "relevant_tables": tables,
                    "similar_queries": [ex.model_dump() for ex in discovered.few_shot_examples],
                    "glossary_terms": {},
                },
            }

        result = perform_discovery(discovery_req)
        return {
            "query": result.query,
            "reasoning": result.reasoning,
            "context": {
                "relevant_tables": [
                    {
                        "schema_name": table.schema_name,
                        "table_name": table.table_name,
                        "description": table.description,
                        "columns": [
                            {
                                "name": col.name,
                                "data_type": col.data_type,
                                "description": col.description
                            } for col in table.columns
                        ]
                    } for table in result.context.relevant_tables
                ],
                "similar_queries": result.context.similar_queries,
                "glossary_terms": result.context.glossary_terms
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test")
def test_endpoint(api_key: str = Depends(verify_api_key)):
    return {"message": "Test endpoint works"}
