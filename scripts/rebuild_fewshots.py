import sys
import os

# Add parent directory to path to allow importing app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.vector_store import get_vector_store
from app.services.settings_service import load_settings
from app.core.config import settings
from pymilvus import connections, utility

def rebuild_fewshots():
    print("Connecting to Milvus...")
    vector_config = load_settings().vector_config
    connections.connect(
        alias="default", 
        host=vector_config.host, 
        port=vector_config.port
    )
    
    collection_name = settings.MILVUS_COLLECTION_FEWSHOT
    
    if utility.has_collection(collection_name):
        print(f"Dropping existing collection: {collection_name}")
        utility.drop_collection(collection_name)
        print("Collection dropped.")
    else:
        print(f"Collection {collection_name} does not exist.")
    
    print("Re-initializing VectorStore to trigger collection creation...")
    # This will trigger _connect_milvus which calls _ensure_fewshot_collection
    vector_store = get_vector_store()
    
    # Verify creation
    if utility.has_collection(collection_name):
        print(f"Successfully recreated collection: {collection_name}")
        print("Done!")
    else:
        print("Error: Collection was not created.")

if __name__ == "__main__":
    rebuild_fewshots()
