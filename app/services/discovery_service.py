from app.models.schemas import DiscoveryRequest, DiscoveryResponse, DiscoveryContext
from app.services.vector_store import get_vector_store

def perform_discovery(request: DiscoveryRequest) -> DiscoveryResponse:
    vector_store = get_vector_store()
    # Search for relevant tables
    schemas = vector_store.search_schemas(request.query, request.top_k)

    # Search for similar queries (specifically SQL examples)
    raw_few_shots = vector_store.search_fewshots(request.query, top_k=3, knowledge_type="sql_query")

    # Transform fewshot results to a simpler format
    similar_queries = []
    for fs in raw_few_shots:
        if isinstance(fs, dict):
            entity = fs.get('entity', {})
            similar_query = {
                "question": entity.get("question", ""),
                "sql": entity.get("sql_query", "")
            }
            similar_queries.append(similar_query)

    context = DiscoveryContext(
        relevant_tables=schemas,
        similar_queries=similar_queries
    )

    return DiscoveryResponse(
        query=request.query,
        reasoning=f"Identified {len(schemas)} relevant tables and {len(similar_queries)} similar queries.",
        context=context
    )
