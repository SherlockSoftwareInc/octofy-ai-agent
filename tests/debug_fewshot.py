from pymilvus import connections, Collection, utility
from app.core.config import settings
from app.services.settings_service import load_settings
import time
import random

def debug_milvus():
    vector_config = load_settings().vector_config
    print(f"Connecting to {vector_config.host}:{vector_config.port}...")
    connections.connect(host=vector_config.host, port=vector_config.port)
    
    name = settings.MILVUS_COLLECTION_FEWSHOT
    print(f"Checking collection: {name}")
    
    if not utility.has_collection(name):
        print("Collection does not exist!")
        return

    collection = Collection(name)
    collection.load()
    
    print(f"Current num_entities: {collection.num_entities}")
    
    # Try Query
    res = collection.query(expr="id >= 0", output_fields=["id", "question"], limit=10)
    print(f"Query Result (Before Insert): {res}")
    
    if not res:
        print("Attempting to Insert Dummy Data...")
        # Dummy Embedding (Size 1536)
        dummy_emb = [random.random() for _ in range(1536)]
        
        data = [
            [dummy_emb], # embedding column
            ["Debug Question"], # question column
            ["SELECT * FROM Debug"] # sql column
        ]
        
        mr = collection.insert(data)
        print(f"Insert Result: {mr}")
        
        print("Flushing...")
        collection.flush()
        print(f"Num entities after flush: {collection.num_entities}")
        
        # Query again with Strong consistency
        res_after = collection.query(expr="id >= 0", output_fields=["id", "question"], consistency_level="Strong")
        print(f"Query Result (After Insert): {res_after}")
        
if __name__ == "__main__":
    try:
        debug_milvus()
    except Exception as e:
        print(f"Error: {e}")
