
import sys
import os

# Add parent dir to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ingest_service import create_milvus_collections, ingest_metadata
from app.services.vector_store import get_vector_store

def seed_data():
    print("1. Rebuilding Vector Store...")
    # This recreates the collections (dropping existing ones)
    create_milvus_collections()

    print("\n2. Syncing Schemas...")
    # This inspects SQL Server and populates the Schema Index
    ingest_metadata()

    print("\n3. Seeding Few-Shot Examples...")
    vector_store = get_vector_store()

    # Example provided by user
    question = "Who is the top customer?"
    sql_query = """SELECT TOP 1
    CompanyName,
    SUM(SaleAmount) AS TotalSales
FROM dbo.[Sales Totals by Amount]
GROUP BY CompanyName
ORDER BY TotalSales DESC;"""

    vector_store.insert_fewshot_item(question, sql_query)
    print(f"Inserted few-shot example: '{question}'")
    
    print("\nSeeding complete.")

if __name__ == "__main__":
    seed_data()
