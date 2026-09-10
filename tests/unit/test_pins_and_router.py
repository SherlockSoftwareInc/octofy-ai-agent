from types import SimpleNamespace

from app.services.object_name_resolver import ObjectNameResolver, ResolvedName
from app.core.constants import FuzzyMatchMinConfidence
from app.core.orchestrator.router import route
from app.core.orchestrator.preprocessing import preprocess
from app.models.pipeline import AgentRequest
from app.core.branch_taxonomy import RouteKind, DiscoveryBranch


class FakeCatalog:
    def list_objects(self):
        return [
            {"schema_name": "dbo", "object_name": "Customers", "object_type": "Table"},
            {"schema_name": "dbo", "object_name": "Orders", "object_type": "Table"},
        ]

    def object_exists(self, schema, name):
        return any(
            o["schema_name"].lower() == schema.lower() and o["object_name"].lower() == name.lower()
            for o in self.list_objects()
        )

    def find_closest(self, name, limit=5):
        from difflib import SequenceMatcher

        scored = []
        for o in self.list_objects():
            cand = f"{o['schema_name']}.{o['object_name']}"
            scored.append({"confidence": SequenceMatcher(None, name.lower(), cand.lower()).ratio(), **o})
        scored.sort(key=lambda x: x["confidence"], reverse=True)
        return scored[:limit]


def test_exact_and_fuzzy_and_missing():
    resolver = ObjectNameResolver(FakeCatalog())
    exact = resolver.resolve("dbo.Customers")
    assert exact.status == "exact"
    fuzzy = resolver.resolve("dbo.Customer")
    assert fuzzy.status in {"fuzzy", "missing"}
    if fuzzy.status == "fuzzy":
        assert fuzzy.confidence >= FuzzyMatchMinConfidence
    missing = resolver.resolve("dbo.NoSuchTableXYZ")
    assert missing.status == "missing"


def test_code_fixing_route():
    ctx = preprocess(AgentRequest(query="fix this", existing_code="SELECT 1", error_message="bad column"))
    decision = route(ctx)
    assert decision.route == RouteKind.CODE_FIXING
    assert decision.skip_discovery is False


def test_optimize_no_discovery_when_existing_code_no_error():
    ctx = preprocess(AgentRequest(query="make it faster", existing_code="SELECT 1"))
    decision = route(ctx)
    assert decision.route == RouteKind.OPTIMIZE
    assert decision.skip_discovery is True


def test_conversational_force_general():
    ctx = preprocess(AgentRequest(query="hello", force_general=True))
    decision = route(ctx)
    assert decision.route == RouteKind.CONVERSATIONAL
    assert decision.immediate_result.discovery_branch == DiscoveryBranch.OFF_TOPIC
