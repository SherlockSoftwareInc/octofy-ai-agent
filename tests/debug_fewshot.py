from app.services.vector_store import get_vector_store


def debug_fewshots():
    vector_store = get_vector_store()
    items = vector_store.get_all_fewshots()
    print(f"few_shots count: {len(items)}")
    for item in items[:10]:
        print(f" - {item.get('id')}: {item.get('question')}")


if __name__ == "__main__":
    try:
        debug_fewshots()
    except Exception as e:
        print(f"Error: {e}")
