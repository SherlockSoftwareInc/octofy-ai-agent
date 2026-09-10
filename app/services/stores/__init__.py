"""Per-source store adapters. Import bundle lazily to avoid circular imports."""

__all__ = ["SourceStores", "build_source_stores", "resolve_source_stores", "get_vector_provider"]


def __getattr__(name):
    if name in {"SourceStores", "build_source_stores", "resolve_source_stores"}:
        from app.services.stores.bundle import SourceStores, build_source_stores, resolve_source_stores

        mapping = {
            "SourceStores": SourceStores,
            "build_source_stores": build_source_stores,
            "resolve_source_stores": resolve_source_stores,
        }
        return mapping[name]
    if name == "get_vector_provider":
        from app.services.stores.provider_factory import get_vector_provider

        return get_vector_provider
    raise AttributeError(name)
