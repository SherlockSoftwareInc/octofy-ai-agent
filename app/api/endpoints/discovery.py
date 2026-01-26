from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import DiscoveryRequest, DiscoveryResponse
from app.services.discovery_service import perform_discovery
from app.core.auth import verify_api_key

router = APIRouter()

@router.post("/discovery")
def discovery_endpoint(request: dict, api_key: str = Depends(verify_api_key)):
    try:
        # Create a DiscoveryRequest-like object
        from app.models.schemas import DiscoveryRequest
        discovery_req = DiscoveryRequest(query=request.get("query", ""), top_k=request.get("top_k", 5))

        # Call the discovery service
        result = perform_discovery(discovery_req)
        # Convert to dict to avoid Pydantic validation issues
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test")
def test_endpoint(api_key: str = Depends(verify_api_key)):
    return {"message": "Test endpoint works"}
