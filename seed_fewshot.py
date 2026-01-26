from app.services.vector_store import get_vector_store
import sys

def seed():
    try:
        print("Initializing Vector Store Service...")
        store = get_vector_store()
        
        question = "Show me all customers"
        sql = "SELECT * FROM Customers"
        
        print(f"Inserting: {question}")
        store.insert_fewshot_item(question, sql)
        print("Insert called successfully.")
        
        print("Verifying via Service...")
        items = store.get_all_fewshots()
        print(f"Found {len(items)} items.")
        for item in items:
            print(f"- {item.get('question')}: {item.get('sql_query')}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    seed()
