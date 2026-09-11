from pathlib import Path

from app.models.pipeline import ScoredObject
from app.services.sql_context_hydrator import SqlContextHydrator
from app.services.stores.skills_folder import markdown_lookup_for_objects, object_markdown_path


def test_object_markdown_path_finds_schema_file(tmp_path: Path):
    schemas = tmp_path / "schemas" / "dbo"
    schemas.mkdir(parents=True)
    target = schemas / "dbo.Products.md"
    target.write_text("# Table: [dbo].[Products]\n\n## Columns\n| ProductID | int |\n", encoding="utf-8")

    found = object_markdown_path(tmp_path, "dbo", "Products")
    assert found == target


def test_markdown_lookup_for_objects_loads_skills_files(tmp_path: Path, monkeypatch):
    (tmp_path / "_data-source.md").write_text("source_id: src-1\n", encoding="utf-8")
    schemas = tmp_path / "schemas" / "dbo"
    schemas.mkdir(parents=True)
    (schemas / "dbo.Products.md").write_text(
        "# Table: [dbo].[Products]\n\n## Columns\n| ProductID | int |\n| CategoryID | int |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.stores.skills_folder.resolve_data_source_folder",
        lambda source_id, skills_root=None: tmp_path,
    )
    obj = ScoredObject(
        schema_name="dbo",
        object_name="Products",
        description="Entity: Table | Name: Products | Description: snippet",
    )
    lookup = markdown_lookup_for_objects("src-1", [obj])
    assert "dbo.products" in lookup
    assert "CategoryID" in lookup["dbo.products"]
    assert obj.markdown and "CategoryID" in obj.markdown


def test_hydrator_prefers_skills_markdown_over_embedding_description():
    obj = ScoredObject(
        schema_name="dbo",
        object_name="Products",
        score=1.0,
        required=True,
        description="Entity: Table | Name: Products | Description: snippet only",
    )
    hydrator = SqlContextHydrator()
    _selected, _supp, schema, _validation = hydrator.build_contexts(
        [obj],
        markdown_lookup={"dbo.products": "# Table: Products\n\n## Columns\n| CategoryID | int |\n"},
    )
    assert "CategoryID" in schema
    assert "snippet only" not in schema


def test_hydrator_unwraps_embedding_description_when_markdown_missing():
    obj = ScoredObject(
        schema_name="dbo",
        object_name="Products",
        score=1.0,
        required=True,
        description="Entity: Table | Name: Products | Description: # Table: Products\n\n## Columns\n| UnitPrice | money |\n",
    )
    hydrator = SqlContextHydrator()
    _selected, _supp, schema, _validation = hydrator.build_contexts([obj])
    assert "UnitPrice" in schema
    assert "Entity: Table" not in schema
