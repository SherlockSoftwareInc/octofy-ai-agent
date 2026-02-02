# Test program for skills-based data object search

from app.services.discovery_service import perform_skills_based_discovery
from app.services.llm_service import get_llm_service
import time

if __name__ == "__main__":
    query = "Find top selling products"
    llm_service = get_llm_service()
    start = time.time()
    result = perform_skills_based_discovery(query, llm_service)
    elapsed = time.time() - start

    print("=== Skills Tables ===")
    for t in result.candidate_tables:
        print(f"{t.schema_name}.{t.table_name} (score={t.score}, matched_by={t.matched_by})")
    print(f"\nSearch completed in {elapsed:.3f} seconds.")

