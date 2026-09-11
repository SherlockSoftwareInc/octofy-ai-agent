"""Clear and recreate the contract few_shots collections."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.stores.provider_factory import get_vector_provider
from app.services.vector_store import refresh_vector_store


def rebuild_fewshots():
    print("Preparing contract few_shots collections...")
    get_vector_provider.cache_clear()
    provider = get_vector_provider()
    if hasattr(provider, "ensure_schema"):
        provider.ensure_schema()

    vector_store = refresh_vector_store()
    vector_store.clear_fewshots_collection()
    print("Cleared few_shots and few_shots_meta.")
    print("Done!")


if __name__ == "__main__":
    rebuild_fewshots()
