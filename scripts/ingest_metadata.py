
import sys
import os

# Add parent dir to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ingest_service import create_milvus_collections, ingest_metadata

if __name__ == "__main__":
    try:
        print("Starting Ingestion Process...")
        create_milvus_collections()
        ingest_metadata()
    except Exception as e:
        print(f"Error: {e}")
