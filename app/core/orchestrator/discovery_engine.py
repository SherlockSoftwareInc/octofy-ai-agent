"""KB-first discovery with column evidence, RRF, caches, data groups."""

from __future__ import annotations

import copy
from typing import Dict, List, Optional

from app.core.branch_taxonomy import DiscoveryBranch, precomputed_related
from app.core.constants import (
    ActiveDataGroupTopN,
    ApplyColumnBoost,
    ApplyColumnBoostCap,
    ColumnDetailValueSeedScore,
    DefaultPrecomputedQueryDirectMatchThreshold,
    DefaultPrecomputedQueryFewShotThreshold,
    KbConfidenceThreshold,
    KbExactMatchThreshold,
    KbScoreThreshold,
    KeywordMatchScore,
    MaxDiscoveryCacheEntries,
    MaxQueryAnalysisCacheEntries,
    MaxRerankTables,
    RelativeColumnScoreThreshold,
    effective_object_search_threshold,
)
from app.models.pipeline import (
    ActiveDataGroupContext,
    DiscoveryResult,
    FewShotExample,
    QueryAnalysis,
    ScoredObject,
)
from app.utils.hashing import as_text_token, discovery_cache_key, query_analysis_cache_key
from app.utils.regexes import complexity_tier
from app.utils.rrf import merge_and_dedup, rrf_merge


def _stringify_terms(values) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in values or []:
        text = as_text_token(item)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


class DiscoveryEngine:
    def __init__(self, stores, llm=None):
        self.stores = stores
        self.llm = llm
        self._discovery_cache: Dict[str, DiscoveryResult] = {}
        self._analysis_cache: Dict[str, QueryAnalysis] = {}

    def clear_analysis_cache(self) -> None:
        self._analysis_cache.clear()

    def kb_exact(self, question: str) -> Optional[FewShotExample]:
        return self.stores.fewshots.try_get_exact(question)

    def precomputed_exact(self, question: str) -> Optional[FewShotExample]:
        return self.stores.vector_search.try_get_precomputed_exact(question)

    def kb_vector_top1(self, question: str) -> Optional[FewShotExample]:
        hits = self.stores.fewshots.search(question, top_k=1, max_distance=KbScoreThreshold)
        return hits[0] if hits else None

    def analyze_query(self, combined_query: str, existing_code: Optional[str], skip: bool = False) -> QueryAnalysis:
        if skip:
            return QueryAnalysis(complexity="simple")
        key = query_analysis_cache_key(combined_query, existing_code)
        if key in self._analysis_cache:
            return self._analysis_cache[key].model_copy(deep=True)
        analysis = QueryAnalysis(complexity=complexity_tier(combined_query))
        if self.llm is not None:
            try:
                data = self.llm.complete_json(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Return JSON keys: keywords, complexity, entities, date_ranges, "
                                "filter_values, extracted_columns. Every list item must be a string, not an object."
                            ),
                        },
                        {"role": "user", "content": combined_query[:2000]},
                    ]
                )
                analysis.keywords = _stringify_terms(data.get("keywords"))
                complexity = data.get("complexity")
                if isinstance(complexity, str) and complexity.strip():
                    analysis.complexity = complexity.strip()
                analysis.entities = _stringify_terms(data.get("entities"))
                analysis.date_ranges = _stringify_terms(data.get("date_ranges"))
                analysis.filter_values = _stringify_terms(data.get("filter_values"))
                cols = []
                seen = set()
                for col in data.get("extracted_columns") or []:
                    c = as_text_token(col).strip("[]\"'`")
                    if "." in c:
                        c = c.split(".")[-1]
                    keyc = c.lower()
                    if c and keyc not in seen:
                        seen.add(keyc)
                        cols.append(c)
                    if len(cols) >= 20:
                        break
                analysis.extracted_columns = cols
            except Exception:
                pass
        if len(self._analysis_cache) >= MaxQueryAnalysisCacheEntries:
            self._analysis_cache.clear()
        self._analysis_cache[key] = analysis
        return analysis.model_copy(deep=True)

    def resolve_active_data_groups(self, query: str) -> ActiveDataGroupContext:
        groups = self.stores.data_groups.search(query, top_n=ActiveDataGroupTopN)
        if not groups:
            scored = self.stores.schema_index.score_data_group_keywords(query, self.stores.data_groups.list())
            groups = [g for g in scored if g.get("overlap", 0) > 0][:ActiveDataGroupTopN]
        members: Dict[str, List[str]] = {}
        for g in groups:
            for member in g.get("members") or []:
                members.setdefault(str(member).lower(), []).append(g.get("group_name") or g.get("group_id"))
        names = [g.get("group_name") or g.get("group_id") for g in groups]
        summary = f"Active data groups: {', '.join(str(n) for n in names)}" if names else ""
        return ActiveDataGroupContext(top_groups=groups, member_groups=members, summary=summary)

    def discover(
        self,
        query: str,
        analysis: QueryAnalysis,
        pins: Optional[List[str]] = None,
        table_override: Optional[List[str]] = None,
        top_k: int = 8,
        existing_sql: Optional[str] = None,
    ) -> DiscoveryResult:
        if table_override:
            objects = [
                ScoredObject(
                    schema_name=self._split(n)[0],
                    object_name=self._split(n)[1],
                    score=1.0,
                    priority=True,
                    required=True,
                )
                for n in table_override
            ]
            return DiscoveryResult(objects=objects, branch=DiscoveryBranch.TABLE_OVERRIDE)

        cache_key = discovery_cache_key(analysis.entities or [query], analysis.complexity, top_k, analysis.extracted_columns)
        if cache_key in self._discovery_cache:
            return self._discovery_cache[cache_key].model_copy(deep=True)

        kb_hits = self.stores.fewshots.search(query, top_k=3, max_distance=KbScoreThreshold)
        best_kb = kb_hits[0] if kb_hits else None
        column_objects = self.discover_with_column_evidence(query, analysis)
        precomputed = self.stores.vector_search.search_precomputed(query)

        if best_kb and (1.0 - best_kb.score) >= KbConfidenceThreshold:
            # kb confidence is 1 - distance when score is distance; FewShotExample.score is distance
            confidence = 1.0 - best_kb.score if best_kb.score <= 1 else best_kb.score
            if best_kb.score <= (1.0 - KbConfidenceThreshold) or confidence >= KbConfidenceThreshold:
                tables = self._objects_from_sql(best_kb.sql)
                branch = DiscoveryBranch.KB_DIRECT
                result = DiscoveryResult(
                    objects=tables or column_objects,
                    branch=branch,
                    few_shot_examples=[best_kb],
                    query_analysis=analysis,
                )
                return self._remember(cache_key, result)

        if best_kb:
            merged = merge_and_dedup(self._objects_from_sql(best_kb.sql) + column_objects)
            result = DiscoveryResult(
                objects=merged[:MaxRerankTables],
                branch=DiscoveryBranch.KB_GAP_FILL,
                few_shot_examples=[best_kb],
                query_analysis=analysis,
            )
            return self._remember(cache_key, result)

        schema_list = self.stores.vector_search.search_objects(query, top_k=top_k)
        value_objects: List[ScoredObject] = []
        for fv in analysis.filter_values:
            for hit in self.stores.values.search(fv, top_k=5):
                value_objects.append(
                    ScoredObject(
                        schema_name=hit.get("schema_name") or "dbo",
                        object_name=hit.get("table_name") or "",
                        score=ColumnDetailValueSeedScore,
                        matched_columns=[hit.get("column_name")] if hit.get("column_name") else [],
                        required=True,
                    )
                )
        fewshot_objects = []
        for ex in kb_hits:
            fewshot_objects.extend(self._objects_from_sql(ex.sql))
        group_ctx = self.resolve_active_data_groups(query)
        group_objects = []
        for g in group_ctx.top_groups:
            for member in g.get("members") or []:
                schema, name = self._split(str(member))
                group_objects.append(ScoredObject(schema_name=schema, object_name=name, score=float(g.get("score") or 0.5)))
        bm25_list = self.stores.bm25.rank(query, schema_list + column_objects)
        merged = rrf_merge(
            {
                "schema_vector": schema_list,
                "value_index": value_objects,
                "few_shot": fewshot_objects,
                "data_group": group_objects,
                "bm25": bm25_list,
            },
            max_results=MaxRerankTables,
        )
        merged = merge_and_dedup(merged + column_objects)
        if pins:
            pin_objs = [
                ScoredObject(schema_name=self._split(p)[0], object_name=self._split(p)[1], score=1.0, priority=True, required=True)
                for p in pins
            ]
            merged = merge_and_dedup(pin_objs + merged)
        branch = DiscoveryBranch.DUAL_PRONG
        member_keys = set(group_ctx.member_groups.keys())
        if any(f"{o.schema_name}.{o.object_name}".lower() in member_keys or o.object_name.lower() in member_keys for o in merged):
            branch = DiscoveryBranch.GROUP_ANCHORED
        examples = list(precomputed[:3])
        if examples and examples[0].score >= DefaultPrecomputedQueryFewShotThreshold and not examples[0].is_exact_match:
            branch = precomputed_related(branch)
        result = DiscoveryResult(
            objects=merged[:MaxRerankTables],
            branch=branch,
            few_shot_examples=examples,
            active_groups=group_ctx,
            query_analysis=analysis,
            value_mappings=[
                {"value": v.get("value"), "table": v.get("table_name"), "column": v.get("column_name")}
                for fv in analysis.filter_values
                for v in self.stores.values.search(fv, top_k=3)
            ],
        )
        return self._remember(cache_key, result)

    def discover_with_column_evidence(self, query: str, analysis: QueryAnalysis) -> List[ScoredObject]:
        objects: Dict[str, ScoredObject] = {}
        # value-index seeds
        for fv in analysis.filter_values:
            for hit in self.stores.values.search(fv, top_k=5):
                key = f"{hit.get('schema_name')}|{hit.get('table_name')}".lower()
                obj = objects.get(key) or ScoredObject(
                    schema_name=hit.get("schema_name") or "dbo",
                    object_name=hit.get("table_name") or "",
                    score=ColumnDetailValueSeedScore,
                )
                col = hit.get("column_name")
                if col and col not in obj.matched_columns:
                    obj.matched_columns.append(col)
                obj.required = True
                objects[key] = obj
        threshold = effective_object_search_threshold()
        if analysis.extracted_columns:
            for col in analysis.extracted_columns:
                hits = self.stores.vector_search.search_columns_scored(col, top_k=20, min_score=threshold)
                self._merge_column_hits(objects, hits)
        else:
            hits = self.stores.vector_search.search_columns_scored(query, top_k=100, min_score=threshold)
            self._merge_column_hits(objects, hits)
        # keyword-token pass
        tokens = [t for t in query.replace(",", " ").split() if t]
        for obj in list(objects.values()):
            for tok in tokens:
                if tok.lower() in " ".join(obj.matched_columns).lower():
                    obj.score = min(ApplyColumnBoostCap, obj.score + KeywordMatchScore * 0)
        for obj in objects.values():
            if obj.matched_columns:
                obj.score = min(ApplyColumnBoostCap, obj.score + ApplyColumnBoost)
                obj.required = True
                if obj.matched_columns:
                    best = 1.0
                    kept = []
                    # relative filter placeholder — keep all matched
                    kept = obj.matched_columns
                    obj.matched_columns = kept
        return list(objects.values())

    def _merge_column_hits(self, objects: Dict[str, ScoredObject], hits: List[dict]) -> None:
        by_parent: Dict[str, List[tuple]] = {}
        for hit in hits:
            if (hit.get("entity_type") or "") != "Column":
                continue
            key = f"{hit.get('schema_name')}|{hit.get('object_name')}".lower()
            score = 1.0 - float(hit.get("_distance") or 1.0)
            by_parent.setdefault(key, []).append((score, hit))
        for key, items in by_parent.items():
            best = max(s for s, _ in items) if items else 0
            obj = objects.get(key) or ScoredObject(
                schema_name=items[0][1].get("schema_name") or "dbo",
                object_name=items[0][1].get("object_name") or "",
                score=best,
                vector_score=1.0 - best,
            )
            for score, hit in items:
                if best and score < best * RelativeColumnScoreThreshold:
                    continue
                col = hit.get("column_name")
                if col and col not in obj.matched_columns:
                    obj.matched_columns.append(col)
            obj.required = True
            objects[key] = obj

    def _objects_from_sql(self, sql: str) -> List[ScoredObject]:
        from app.utils.sql_normalization import extract_sql_object_refs

        objs = []
        for ref in extract_sql_object_refs(sql):
            schema, name = self._split(ref)
            objs.append(ScoredObject(schema_name=schema, object_name=name, score=0.9))
        return objs

    def _split(self, name: str) -> tuple:
        cleaned = name.replace("[", "").replace("]", "")
        if "." in cleaned:
            s, o = cleaned.split(".", 1)
            return s, o
        return "dbo", cleaned

    def _remember(self, key: str, result: DiscoveryResult) -> DiscoveryResult:
        if len(self._discovery_cache) >= MaxDiscoveryCacheEntries:
            self._discovery_cache.clear()
        self._discovery_cache[key] = result
        return result.model_copy(deep=True)
