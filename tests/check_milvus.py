from pymilvus import connections
from app.services.settings_service import load_settings

def check_milvus():
    vector_config = load_settings().vector_config
    print(f"Connecting to {vector_config.host}:{vector_config.port}...")
    try:
        connections.connect(alias="default", host=vector_config.host, port=vector_config.port)
        print("Success!")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    check_milvus()
