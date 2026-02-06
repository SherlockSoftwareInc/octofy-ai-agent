# Knowledge-Base-First Discovery Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current sequential multi-source discovery pipeline (steps 5-7 in `generate_sql_for_request`) with a knowledge-base-first strategy that searches fewshots first, uses LLM evaluation to determine if results are sufficient, and only falls back to full discovery when knowledge base has no relevant results.

**Architecture:** The discovery block in `generate_sql_for_request()` (lines 1491-1534) is replaced inline with a three-branch flow: (1) search knowledge base first with L2 < 0.5 threshold, (2a) if hits found, LLM evaluates whether they're sufficient for direct SQL generation or need gap-filling, (2b) if no hits, fall back to current dual-source discovery (value index + schema index). A new `evaluate_example_relevance()` method on the LLM service handles structured assessment. Branch 1.1.1 (high confidence) bypasses all validation and goes directly to prompt construction. Branch 1.1.2 (gap-filling) does targeted supplementary search then jumps to Step 10 (join-path sufficiency validation), skipping Steps 8-9.

**Tech Stack:** Python 3.8+, FastAPI, Pydantic, LiteLLM/OpenAI, Milvus vector DB

---

## Prerequisite: Understanding the Current Flow

The discovery logic lives inline in `generate_sql_for_request()` at `app/services/generation_service.py:1491-1534`:

```
Current Steps (Sequential):
  Step 5: extract_filter_values() via LLM -> search_values() per entity
  Step 6: search_fewshots() -> extract_tables_from_sql() via LLM -> search_schemas()
  Step 7: rerank_and_select_tables() -> hydrate_discovery_context() -> expand_context_with_neighbors()
  Step 8: validate_schema_completeness() (FK reference check)
  Step 9: lookup_values_for_query() (value index)
  Step 10: validate_schema_with_join_paths() (sufficiency)
```

After refactor:
```
New Flow (Sequential + Conditional):
  Step 5: search_fewshots() with L2 < 0.5 threshold check
  
  IF hits found (Branch 1.1):
    Step 6: evaluate_example_relevance() via LLM (structured JSON)
    
    IF sufficient (Branch 1.1.1 - high confidence):
      -> Extract tables from fewshot SQL
      -> Hydrate context from those tables
      -> Skip Steps 8, 9, 10 entirely
      -> Proceed directly to prompt construction (Stage 3)
    
    IF insufficient (Branch 1.1.2 - gap filling):
      -> Use LLM's gap analysis (missing_entities, missing_tables)
      -> Run targeted schema_index + value_index search on gap keywords
      -> Hydrate combined context
      -> Skip Steps 8, 9
      -> Jump to Step 10 (join-path sufficiency validation)
  
  IF no hits (Branch 1.2 - dual prong):
    -> Run existing Steps 5-7 (NER + value + schema + rerank)
    -> Continue to Steps 8, 9, 10 as before
```

---

## Task 1: Add Pydantic Models for KB Assessment

**Files:**
- Modify: `app/models/schemas.py:560-570` (near ThreeProngedResult)

**Step 1: Add the `KBAssessment` model**

Add the following model after the `ThreeProngedResult` class (around line 570):

```python
class KBAssessment(BaseModel):
    """Result of LLM evaluation of knowledge base examples against user query"""
    is_sufficient: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    adjustments_needed: List[str] = []  # e.g., ["Change date filter to 2024", "Add GROUP BY region"]
    missing_entities: List[str] = []  # Entities/dimensions not covered by the KB example
    missing_tables: List[str] = []  # Tables needed but not in the KB SQL
    suggested_search_terms: List[str] = []  # Terms to search schema/value index for gap-filling
    original_sql: str = ""  # The SQL from the knowledge base example
    original_question: str = ""  # The question from the knowledge base example
```

**Step 2: Run validation**

Run: `python -c "from app.models.schemas import KBAssessment; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add app/models/schemas.py
git commit -m "feat(models): add KBAssessment model for knowledge-base-first discovery"
```

---

## Task 2: Add `evaluate_example_relevance()` to LLM Service

**Files:**
- Modify: `app/services/llm_service.py:12-43` (LLMServiceBase abstract class)
- Modify: `app/services/llm_service.py:45-91` (OpenAILLMService - add implementation)
- Modify: `app/services/llm_service.py:700-1337` (LiteLLMService - add implementation)

**Step 1: Add abstract method to `LLMServiceBase`**

In `app/services/llm_service.py`, add the following abstract method after `validate_schema_with_join_paths` (around line 43):

```python
    @abstractmethod
    def evaluate_example_relevance(self, user_query: str, kb_examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate if knowledge base examples can answer the user's query."""
        pass
```

**Step 2: Add implementation to `OpenAILLMService`**

Add the following method to the `OpenAILLMService` class (after `validate_schema_references`, around line 200):

```python
    def evaluate_example_relevance(self, user_query: str, kb_examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate if knowledge base SQL examples can answer the user's query.
        Returns structured assessment with sufficiency judgment and gap analysis.
        """
        import json as json_module
        
        # Build examples text
        examples_text = ""
        for i, ex in enumerate(kb_examples, 1):
            entity = ex.get('entity', ex)
            question = entity.get('question', '')
            sql = entity.get('sql_query', '')
            score = ex.get('score', 'N/A')
            examples_text += f"\n--- Example {i} (similarity score: {score}) ---\n"
            examples_text += f"Question: {question}\n"
            examples_text += f"SQL:\n```sql\n{sql}\n```\n"
        
        prompt = f"""You are a senior SQL expert performing a knowledge base evaluation.

### USER'S NEW QUESTION
{user_query}

### KNOWLEDGE BASE EXAMPLES
{examples_text}

### TASK
Evaluate whether the knowledge base SQL examples above can answer the user's new question.

Consider:
1. Does the SQL retrieve the right data entities (tables, columns)?
2. Are the filters/conditions compatible or easily adjustable?
3. Are there missing dimensions, metrics, or entities that the SQL doesn't cover?

### OUTPUT FORMAT (JSON only, no markdown)
{{
  "is_sufficient": true/false,
  "confidence": 0.0-1.0,
  "adjustments_needed": ["list of minor SQL tweaks needed, e.g. 'change date filter'"],
  "missing_entities": ["entities/dimensions not covered by examples"],
  "missing_tables": ["table names that would be needed but are not in the SQL"],
  "suggested_search_terms": ["terms to search for missing context"]
}}

### RULES
- is_sufficient: true ONLY if the SQL can answer the question with minor tweaks (filter changes, column additions from SAME tables)
- is_sufficient: false if the query needs entirely different tables or complex structural changes
- confidence: 0.9+ for exact/near-exact matches, 0.7-0.9 for tweakable, <0.7 for insufficient
- missing_entities: only populate if is_sufficient is false
- suggested_search_terms: keywords to search schema/value indexes for missing data
"""
        
        try:
            if self.client is None:
                # Mock mode
                return {
                    "is_sufficient": False,
                    "confidence": 0.0,
                    "adjustments_needed": [],
                    "missing_entities": [],
                    "missing_tables": [],
                    "suggested_search_terms": []
                }
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a SQL expert evaluating knowledge base relevance. Respond with JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                timeout=30
            )
            
            content = response.choices[0].message.content.strip()
            
            # Log the interaction
            log_messages = [
                {"role": "system", "content": "SQL expert evaluating KB relevance"},
                {"role": "user", "content": prompt}
            ]
            log_llm_interaction(log_messages, content)
            
            # Parse JSON response
            # Strip markdown code fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
            
            result = json_module.loads(content)
            return result
            
        except json_module.JSONDecodeError as e:
            logging.error(f"Failed to parse KB assessment JSON: {e}. Raw: {content}")
            return {
                "is_sufficient": False,
                "confidence": 0.0,
                "adjustments_needed": [],
                "missing_entities": [],
                "missing_tables": [],
                "suggested_search_terms": []
            }
        except Exception as e:
            logging.error(f"Error in evaluate_example_relevance: {e}")
            return {
                "is_sufficient": False,
                "confidence": 0.0,
                "adjustments_needed": [],
                "missing_entities": [],
                "missing_tables": [],
                "suggested_search_terms": []
            }
```

**Step 3: Add implementation to `LiteLLMService`**

Add the same method to `LiteLLMService` class (after `extract_filter_values`, around line 1337). The implementation is identical except it uses `litellm.completion()` instead of `self.client.chat.completions.create()`:

```python
    def evaluate_example_relevance(self, user_query: str, kb_examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate if knowledge base SQL examples can answer the user's query.
        Returns structured assessment with sufficiency judgment and gap analysis.
        """
        import json as json_module
        
        # Build examples text
        examples_text = ""
        for i, ex in enumerate(kb_examples, 1):
            entity = ex.get('entity', ex)
            question = entity.get('question', '')
            sql = entity.get('sql_query', '')
            score = ex.get('score', 'N/A')
            examples_text += f"\n--- Example {i} (similarity score: {score}) ---\n"
            examples_text += f"Question: {question}\n"
            examples_text += f"SQL:\n```sql\n{sql}\n```\n"
        
        prompt = f"""You are a senior SQL expert performing a knowledge base evaluation.

### USER'S NEW QUESTION
{user_query}

### KNOWLEDGE BASE EXAMPLES
{examples_text}

### TASK
Evaluate whether the knowledge base SQL examples above can answer the user's new question.

Consider:
1. Does the SQL retrieve the right data entities (tables, columns)?
2. Are the filters/conditions compatible or easily adjustable?
3. Are there missing dimensions, metrics, or entities that the SQL doesn't cover?

### OUTPUT FORMAT (JSON only, no markdown)
{{
  "is_sufficient": true/false,
  "confidence": 0.0-1.0,
  "adjustments_needed": ["list of minor SQL tweaks needed, e.g. 'change date filter'"],
  "missing_entities": ["entities/dimensions not covered by examples"],
  "missing_tables": ["table names that would be needed but are not in the SQL"],
  "suggested_search_terms": ["terms to search for missing context"]
}}

### RULES
- is_sufficient: true ONLY if the SQL can answer the question with minor tweaks (filter changes, column additions from SAME tables)
- is_sufficient: false if the query needs entirely different tables or complex structural changes
- confidence: 0.9+ for exact/near-exact matches, 0.7-0.9 for tweakable, <0.7 for insufficient
- missing_entities: only populate if is_sufficient is false
- suggested_search_terms: keywords to search schema/value indexes for missing data
"""
        
        try:
            response = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a SQL expert evaluating knowledge base relevance. Respond with JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=30
            )
            
            content = response.choices[0].message.content.strip()
            
            # Log the interaction
            log_messages = [
                {"role": "system", "content": "SQL expert evaluating KB relevance"},
                {"role": "user", "content": prompt}
            ]
            log_llm_interaction(log_messages, content)
            
            # Parse JSON response  
            # Strip markdown code fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
            
            result = json_module.loads(content)
            return result
            
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                logging.warning(f"LLM timeout in evaluate_example_relevance after 30s: {e}")
            else:
                logging.error(f"LLM Error in evaluate_example_relevance: {e}")
            return {
                "is_sufficient": False,
                "confidence": 0.0,
                "adjustments_needed": [],
                "missing_entities": [],
                "missing_tables": [],
                "suggested_search_terms": []
            }
```

**Step 4: Verify import works**

Run: `python -c "from app.services.llm_service import get_llm_service; svc = get_llm_service(); print(hasattr(svc, 'evaluate_example_relevance'))"`
Expected: `True`

**Step 5: Commit**

```bash
git add app/services/llm_service.py
git commit -m "feat(llm): add evaluate_example_relevance() for KB-first discovery assessment"
```

---

## Task 3: Add `search_fewshots_with_threshold()` to Vector Store

**Files:**
- Modify: `app/services/vector_store.py:526-563` (near existing `search_fewshots`)

**Step 1: Add threshold-aware fewshot search**

Add the following method to the `MilvusVectorStore` class, after the existing `search_fewshots` method (after line 563):

```python
    def search_fewshots_with_threshold(
        self, 
        query: str, 
        top_k: int = 3, 
        knowledge_type: Optional[str] = None,
        score_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search few-shot examples with L2 distance threshold filtering.
        Only returns results with L2 distance < score_threshold.
        
        Args:
            query: Search query text
            top_k: Maximum results to return
            knowledge_type: Optional filter (e.g., "sql_query")
            score_threshold: Maximum L2 distance to include (lower = more similar)
            
        Returns:
            List of matching fewshot items with score < threshold
        """
        # Use existing search
        all_results = self.search_fewshots(query, top_k=top_k, knowledge_type=knowledge_type)
        
        # Filter by threshold
        filtered = [r for r in all_results if r.get('score', float('inf')) < score_threshold]
        
        if filtered:
            logging.info(
                f"[KB Search] {len(filtered)}/{len(all_results)} results passed threshold {score_threshold}. "
                f"Best score: {filtered[0].get('score', 'N/A')}"
            )
        else:
            scores = [r.get('score', 'N/A') for r in all_results]
            logging.info(
                f"[KB Search] 0/{len(all_results)} results passed threshold {score_threshold}. "
                f"Scores: {scores}"
            )
        
        return filtered
```

**Step 2: Verify**

Run: `python -c "from app.services.vector_store import get_vector_store; vs = get_vector_store(); print(hasattr(vs, 'search_fewshots_with_threshold'))"`
Expected: `True`

**Step 3: Commit**

```bash
git add app/services/vector_store.py
git commit -m "feat(vector_store): add search_fewshots_with_threshold() with L2 distance filtering"
```

---

## Task 4: Refactor Discovery Block in `generate_sql_for_request()`

This is the core task. We replace the inline discovery block at lines 1491-1534 with the knowledge-base-first logic.

**Files:**
- Modify: `app/services/generation_service.py:1491-1534` (the `else` block under `elif request.context`)

**Step 1: Replace the discovery block**

Replace the entire block from line 1491 (`# Multi-Source Discovery`) through line 1534 (`context = hydrate_discovery_context(expanded_list, similar_queries)`) with the following:

```python
        # ====================================================================
        # KNOWLEDGE-BASE-FIRST DISCOVERY (Sequential + Conditional)
        # ====================================================================
        
        # STEP 1: Knowledge Base Priority Search
        yield AgentStatus(step_id=5, message="Searching knowledge base for similar queries...")
        kb_results = vector_store.search_fewshots_with_threshold(
            request.query, 
            top_k=3, 
            knowledge_type="sql_query",
            score_threshold=0.5  # L2 distance threshold
        )
        
        # Track which discovery branch was taken for logging
        discovery_branch = None
        kb_assessment = None
        
        if kb_results:
            # ============================================================
            # BRANCH 1.1: Knowledge Base Hit - LLM Evaluation
            # ============================================================
            yield AgentStatus(step_id=6, message="Evaluating knowledge base examples with AI...")
            logging.info(f"[KB-First] Found {len(kb_results)} KB results. Evaluating relevance...")
            
            kb_assessment = llm_service.evaluate_example_relevance(request.query, kb_results)
            
            is_sufficient = kb_assessment.get("is_sufficient", False)
            confidence = kb_assessment.get("confidence", 0.0)
            
            if is_sufficient and confidence >= 0.7:
                # ========================================================
                # BRANCH 1.1.1: High Confidence - Direct to Prompt
                # ========================================================
                discovery_branch = "kb_direct"
                logging.info(f"[KB-First] HIGH CONFIDENCE ({confidence}). Using KB example directly.")
                yield AgentStatus(step_id=6, message=f"Found highly relevant example (confidence: {confidence:.0%}). Using as reference...")
                
                # Extract tables from the best KB example's SQL
                best_example = kb_results[0]
                best_entity = best_example.get('entity', best_example)
                best_sql = best_entity.get('sql_query', '')
                
                # Get table names from the KB SQL
                kb_sql_tables = llm_service.extract_tables_from_sql([best_sql]) if best_sql else []
                
                # Format similar queries from KB results for context
                similar_queries = []
                for r in kb_results:
                    entity = r.get('entity', r)
                    similar_queries.append({
                        "question": entity.get("question", ""),
                        "sql": entity.get("sql_query", "")
                    })
                
                # Hydrate context using only the KB-referenced tables
                if kb_sql_tables:
                    context = hydrate_discovery_context(kb_sql_tables, similar_queries)
                else:
                    # Fallback: use similar queries without specific table hydration
                    context = DiscoveryContext(
                        relevant_tables=[],
                        similar_queries=similar_queries
                    )
                
                logging.info(f"[KB-First] Branch 1.1.1 complete. Tables: {kb_sql_tables}")
                
            else:
                # ========================================================
                # BRANCH 1.1.2: Gap Filling - Targeted Supplementary Search
                # ========================================================
                discovery_branch = "kb_gap_fill"
                missing_entities = kb_assessment.get("missing_entities", [])
                missing_tables = kb_assessment.get("missing_tables", [])
                search_terms = kb_assessment.get("suggested_search_terms", [])
                
                logging.info(
                    f"[KB-First] INSUFFICIENT ({confidence}). "
                    f"Missing entities: {missing_entities}, Missing tables: {missing_tables}, "
                    f"Search terms: {search_terms}"
                )
                yield AgentStatus(step_id=6, message="Knowledge base example needs supplementation. Searching for missing context...")
                
                # Extract tables from KB examples as a starting point
                kb_sql_list = []
                for r in kb_results:
                    entity = r.get('entity', r)
                    sql = entity.get('sql_query', '')
                    if sql:
                        kb_sql_list.append(sql)
                
                kb_tables = llm_service.extract_tables_from_sql(kb_sql_list) if kb_sql_list else []
                
                # Build search keywords from KB tables + LLM gap analysis
                gap_keywords = list(set(missing_entities + missing_tables + search_terms))
                
                # Targeted supplementary search using gap keywords
                supplementary_tables = []
                supplementary_value_tables = []
                
                for keyword in gap_keywords[:5]:  # Limit to 5 gap searches
                    # Schema index search
                    schema_hits = vector_store.search_schemas(keyword, top_k=3)
                    for s in schema_hits:
                        full_name = f"{s.schema_name}.{s.table_name}"
                        if full_name not in supplementary_tables:
                            supplementary_tables.append(full_name)
                    
                    # Value index search
                    value_hits = vector_store.search_values(keyword, top_k=3)
                    for v in value_hits:
                        entity = v.get('entity', v)
                        table_name = entity.get('table_name', '')
                        schema_name = entity.get('schema_name', 'dbo')
                        if table_name:
                            full_name = f"{schema_name}.{table_name}"
                            if full_name not in supplementary_value_tables:
                                supplementary_value_tables.append(full_name)
                
                # Combine KB tables with supplementary discoveries
                all_tables = list(set(kb_tables + supplementary_tables + supplementary_value_tables))
                
                logging.info(
                    f"[KB-First] Gap fill found {len(supplementary_tables)} schema + "
                    f"{len(supplementary_value_tables)} value tables. "
                    f"Combined: {len(all_tables)} tables."
                )
                
                # Format similar queries from KB results
                similar_queries = []
                for r in kb_results:
                    entity = r.get('entity', r)
                    similar_queries.append({
                        "question": entity.get("question", ""),
                        "sql": entity.get("sql_query", "")
                    })
                
                # Hydrate context
                context = hydrate_discovery_context(all_tables, similar_queries)
                
                yield AgentStatus(step_id=7, message=f"Supplementary discovery complete. Found {len(context.relevant_tables)} tables.")
        
        if not kb_results:
            # ============================================================
            # BRANCH 1.2: No KB Hit - Dual-Prong Strategy (Original Flow)
            # ============================================================
            discovery_branch = "dual_prong"
            logging.info("[KB-First] No KB results passed threshold. Falling back to dual-prong discovery.")
            
            # 1. NER & Value Discovery (Focused)
            yield AgentStatus(step_id=5, message="No knowledge base match. Identifying filter values and entities...")
            filter_values = llm_service.extract_filter_values(request.query)
            value_tables = []
            if filter_values:
                logging.info(f"Discovery: Extracted filter values: {filter_values}")
                for val in filter_values:
                    v_res = vector_store.search_values(val, top_k=3)
                    value_tables.extend([f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in v_res if r.get('table_name')])
            else:
                value_results = vector_store.search_values(request.query, top_k=5)
                value_tables = [f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in value_results if r.get('table_name')]
                
            # 2. Few-Shot Discovery (broader search, no threshold)
            yield AgentStatus(step_id=6, message="Searching knowledge base for similar queries...")
            similar_queries = vector_store.search_fewshots(request.query, top_k=3, knowledge_type="sql_query")
            few_shot_sqls = [q.get('sql_query', '') or q.get('sql', '') for q in similar_queries]
            few_shot_tables = llm_service.extract_tables_from_sql(few_shot_sqls)
            
            # 3. Schema Index Discovery
            schema_results = vector_store.search_schemas(request.query, top_k=5)
            schema_tables = [f"{s.schema_name}.{s.table_name}" for s in schema_results]
            
            # 4. Re-rank and Filter
            final_table_list = rerank_and_select_tables(few_shot_tables, value_tables, schema_tables)
            logging.info(f"Discovery: Selected tables after reranking: {final_table_list}")
            
            # 5. Hydrate Context (Initial)
            context = hydrate_discovery_context(final_table_list, similar_queries)
            
            # 6. Path Finding (Context Expansion)
            yield AgentStatus(step_id=7, message="Analyzing schema relationships and path finding...")
            expanded_list = expand_context_with_neighbors(final_table_list, request.query)
            if len(expanded_list) > len(final_table_list):
                logging.info(f"Discovery: Expanded context from {len(final_table_list)} to {len(expanded_list)} tables.")
                context = hydrate_discovery_context(expanded_list, similar_queries)
```

**Step 2: Modify post-discovery validation to respect branch routing**

The code after the discovery block (lines 1536-1712) handles Steps 8, 9, and 10. We need to add branch-aware gating. Replace the block starting at `if not use_table_override:` (line 1536) through the end of Step 10 (line 1712) with:

```python
    if not use_table_override:
        # Branch-aware validation routing
        if discovery_branch == "kb_direct":
            # BRANCH 1.1.1: Skip Steps 8, 9, 10 entirely - high confidence KB match
            logging.info("[KB-First] Branch 1.1.1: Skipping all validation (Steps 8-10). Direct to prompt.")
            value_mappings = {}
            yield AgentStatus(step_id=8, message="High-confidence knowledge base match. Skipping validation...")
            
        elif discovery_branch == "kb_gap_fill":
            # BRANCH 1.1.2: Skip Steps 8, 9 - jump to Step 10 (sufficiency validation)
            logging.info("[KB-First] Branch 1.1.2: Skipping Steps 8-9. Running Step 10 (sufficiency).")
            value_mappings = {}
            
            # Jump directly to Step 10: Schema Sufficiency with Join-Path Validation
            from app.core.config import settings as app_settings
            use_join_path = getattr(app_settings, 'ENABLE_JOIN_PATH_VALIDATION', True)
            
            if use_join_path:
                yield AgentStatus(step_id=10, message="Validating schema sufficiency with join-path analysis...")
                
                sufficiency_result = llm_service.validate_schema_with_join_paths(
                    user_query=request.query,
                    schemas=context.relevant_tables,
                    code_type="sql"
                )
            else:
                yield AgentStatus(step_id=10, message="Validating schema sufficiency for query requirements...")
                
                sufficiency_result = llm_service.check_schema_sufficiency(
                    user_query=request.query,
                    schemas=context.relevant_tables,
                    code_type="sql"
                )
            
            result_status = sufficiency_result.get("status")
            
            if result_status in ("insufficient_data", "insufficient_joins"):
                missing_points = sufficiency_result.get("missing_data_points", []) or sufficiency_result.get("validation_details", [])
                search_suggestions = sufficiency_result.get("search_suggestions", [])
                missing_logic = sufficiency_result.get("missing_logic")
                
                if result_status == "insufficient_joins" and missing_logic:
                    logging.info(f"Join-path validation failed. Missing logic: {missing_logic}")
                else:
                    logging.info(f"Schema sufficiency check failed. Missing: {[p.get('name', p.get('requirement', '')) for p in missing_points]}")
                
                if search_suggestions:
                    yield AgentStatus(step_id=10, message=f"Missing data detected. Expanding search...")
                    
                    tables_added, context = expand_context_for_missing_data(
                        context, 
                        search_suggestions,
                        max_suggestions=5
                    )
                    
                    if tables_added:
                        yield AgentStatus(step_id=10, message=f"Added {len(tables_added)} tables: {', '.join(tables_added[:3])}{'...' if len(tables_added) > 3 else ''}")
                        
                        if use_join_path:
                            sufficiency_result = llm_service.validate_schema_with_join_paths(
                                user_query=request.query,
                                schemas=context.relevant_tables,
                                code_type="sql"
                            )
                        else:
                            sufficiency_result = llm_service.check_schema_sufficiency(
                                user_query=request.query,
                                schemas=context.relevant_tables,
                                code_type="sql"
                            )
                        result_status = sufficiency_result.get("status")
                
                # If still insufficient after expansion, inform user
                if result_status in ("insufficient_data", "insufficient_joins"):
                    if "missing_data_points" in sufficiency_result:
                        missing_names = [p.get("name", "unknown") for p in sufficiency_result.get("missing_data_points", [])]
                    else:
                        missing_names = [d.get("requirement", "unknown") for d in sufficiency_result.get("validation_details", []) if not d.get("found", True)]
                    
                    analysis = sufficiency_result.get("analysis", "Required data not found in available schemas.")
                    missing_logic_msg = sufficiency_result.get("missing_logic", "")
                    
                    missing_list = "\n".join([f"- {name}" for name in missing_names])
                    
                    explanation = f"**Schema Validation Failed**\n\nI analyzed your request but cannot find the required data in the available schemas.\n\n**Missing data points:**\n{missing_list}\n\n**Analysis:** {analysis}"
                    if missing_logic_msg:
                        explanation += f"\n\n**Join issue:** {missing_logic_msg}"
                    
                    result = GenerateSQLResponse(
                        sql="",
                        explanation=explanation,
                        query_type="database",
                        context_text=f"Sufficiency check failed. Missing: {', '.join(missing_names)}"
                    )
                    yield {"type": "result", "payload": result}
                    yield {"type": "done"}
                    return
            
            yield AgentStatus(step_id=10, message="Schema sufficiency validated. Proceeding with generation...")
            
        else:
            # BRANCH 1.2 (dual_prong) or fallback: Run full validation pipeline
            # Stage 2.3: Schema Completeness Validation
            yield AgentStatus(step_id=8, message="Validating schema completeness...")
            is_complete, missing_tables, validation_analysis = validate_schema_completeness(
                context, 
                request.query, 
                llm_service
            )
            
            # If missing tables detected, attempt auto-discovery
            if not is_complete and missing_tables:
                logging.info(f"Schema validation found missing tables: {missing_tables}")
                logging.info(f"Validation analysis: {validation_analysis}")
                
                discovery_feedback = ""
                tables_added = []
                tables_not_found = []
                
                for missing_table in missing_tables[:5]:
                    try:
                        disc_res = perform_discovery(DiscoveryRequest(query=missing_table, top_k=3))
                        
                        newly_added = False
                        for table in disc_res.context.relevant_tables:
                            table_full_name = f"{table.schema_name}.{table.table_name}"
                            
                            if not any(t.table_name == table.table_name and t.schema_name == table.schema_name 
                                      for t in context.relevant_tables):
                                context.relevant_tables.append(table)
                                discovery_feedback += f"\n- Auto-discovered and added: {table_full_name}"
                                tables_added.append(table_full_name)
                                newly_added = True
                                logging.info(f"Auto-discovered missing table: {table_full_name}")
                        
                        if not newly_added:
                            already_present = any(
                                missing_table.lower() in f"{t.schema_name}.{t.table_name}".lower()
                                for t in context.relevant_tables
                            )
                            if not already_present:
                                tables_not_found.append(missing_table)
                                
                    except Exception as e:
                        logging.error(f"Error discovering missing table {missing_table}: {e}")
                        tables_not_found.append(missing_table)
                
                if tables_not_found:
                    missing_list = "\n".join([f"- {t}" for t in tables_not_found])
                    result = GenerateSQLResponse(
                        sql="",
                        explanation=f"""I detected that the following referenced tables are missing from the database schema index:

{missing_list}

**Reason:** {validation_analysis}

**Next Steps:**
1. Please ensure these tables exist in your database
2. Go to the Schema Management page and sync these table schemas
3. Then try your query again

Alternatively, if these table references are incorrect, please rephrase your query.""",
                        query_type="database",
                        context_text=f"Missing schemas: {', '.join(tables_not_found)}"
                    )
                    yield {"type": "result", "payload": result}
                    yield {"type": "done"}
                    return
                
                if tables_added:
                    logging.info(f"Auto-discovery successful. Added tables: {tables_added}")
            
            # Stage 2.5: Value Index Lookup
            yield AgentStatus(step_id=9, message="Checking value index for specific data mappings...")
            value_mappings = lookup_values_for_query(request.query)
            
            # Stage 2.6: Schema Sufficiency Pre-Flight Check
            from app.core.config import settings as app_settings
            use_join_path = getattr(app_settings, 'ENABLE_JOIN_PATH_VALIDATION', True)
            
            if use_join_path:
                yield AgentStatus(step_id=10, message="Validating schema sufficiency with join-path analysis...")
                
                sufficiency_result = llm_service.validate_schema_with_join_paths(
                    user_query=request.query,
                    schemas=context.relevant_tables,
                    code_type="sql"
                )
            else:
                yield AgentStatus(step_id=10, message="Validating schema sufficiency for query requirements...")
                
                sufficiency_result = llm_service.check_schema_sufficiency(
                    user_query=request.query,
                    schemas=context.relevant_tables,
                    code_type="sql"
                )
            
            result_status = sufficiency_result.get("status")
            
            if result_status in ("insufficient_data", "insufficient_joins"):
                missing_points = sufficiency_result.get("missing_data_points", []) or sufficiency_result.get("validation_details", [])
                search_suggestions = sufficiency_result.get("search_suggestions", [])
                missing_logic = sufficiency_result.get("missing_logic")
                
                if result_status == "insufficient_joins" and missing_logic:
                    logging.info(f"Join-path validation failed. Missing logic: {missing_logic}")
                else:
                    logging.info(f"Schema sufficiency check failed. Missing: {[p.get('name', p.get('requirement', '')) for p in missing_points]}")
                
                if search_suggestions:
                    yield AgentStatus(step_id=10, message=f"Missing data detected. Expanding search...")
                    
                    tables_added, context = expand_context_for_missing_data(
                        context, 
                        search_suggestions,
                        max_suggestions=5
                    )
                    
                    if tables_added:
                        yield AgentStatus(step_id=10, message=f"Added {len(tables_added)} tables: {', '.join(tables_added[:3])}{'...' if len(tables_added) > 3 else ''}")
                        
                        if use_join_path:
                            sufficiency_result = llm_service.validate_schema_with_join_paths(
                                user_query=request.query,
                                schemas=context.relevant_tables,
                                code_type="sql"
                            )
                        else:
                            sufficiency_result = llm_service.check_schema_sufficiency(
                                user_query=request.query,
                                schemas=context.relevant_tables,
                                code_type="sql"
                            )
                        result_status = sufficiency_result.get("status")
                
                if result_status in ("insufficient_data", "insufficient_joins"):
                    if "missing_data_points" in sufficiency_result:
                        missing_names = [p.get("name", "unknown") for p in sufficiency_result.get("missing_data_points", [])]
                    else:
                        missing_names = [d.get("requirement", "unknown") for d in sufficiency_result.get("validation_details", []) if not d.get("found", True)]
                    
                    analysis = sufficiency_result.get("analysis", "Required data not found in available schemas.")
                    missing_logic_msg = sufficiency_result.get("missing_logic", "")
                    
                    missing_list = "\n".join([f"- {name}" for name in missing_names])
                    
                    explanation = f"**Schema Validation Failed**\n\nI analyzed your request but cannot find the required data in the available schemas.\n\n**Missing data points:**\n{missing_list}\n\n**Analysis:** {analysis}"
                    if missing_logic_msg:
                        explanation += f"\n\n**Join issue:** {missing_logic_msg}"
                    
                    result = GenerateSQLResponse(
                        sql="",
                        explanation=explanation,
                        query_type="database",
                        context_text=f"Sufficiency check failed. Missing: {', '.join(missing_names)}"
                    )
                    yield {"type": "result", "payload": result}
                    yield {"type": "done"}
                    return
            
            yield AgentStatus(step_id=10, message="Schema sufficiency validated. Proceeding with generation...")
    else:
        value_mappings = {}
```

**Important:** The `else:` at the very end (for `use_table_override == True`) must set `value_mappings = {}` just as the current code does at line 1620.

**Step 3: Verify the file parses**

Run: `python -c "import app.services.generation_service; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add app/services/generation_service.py
git commit -m "feat(discovery): implement knowledge-base-first discovery with three-branch routing"
```

---

## Task 5: Add Discovery Branch Metadata to Response

**Files:**
- Modify: `app/models/schemas.py:153-159` (GenerateSQLResponse model)
- Modify: `app/services/generation_service.py` (where result is yielded on success, around line 1931)

**Step 1: Add `discovery_branch` field to GenerateSQLResponse**

In `app/models/schemas.py`, add a new optional field to `GenerateSQLResponse`:

```python
class GenerateSQLResponse(BaseModel):
    sql: str
    explanation: Optional[str] = None
    query_type: str = "database"  # "database" or "general"
    context_text: Optional[str] = None
    context_history: Optional[List[str]] = None
    objects: Optional[List[SearchObject]] = None
    discovery_branch: Optional[str] = None  # "kb_direct", "kb_gap_fill", or "dual_prong"
```

**Step 2: Pass discovery_branch into the successful result**

In `generation_service.py`, in the SQL generation loop where `is_valid` is True (around line 1931), update the result construction:

Find the block:
```python
            result = GenerateSQLResponse(
                sql=sql,
                explanation="The following code might be able to retrieve the data you requested.",
                query_type="database",
                context_text=current_prompt,
                context_history=current_context_history
            )
```

Replace with:
```python
            result = GenerateSQLResponse(
                sql=sql,
                explanation="The following code might be able to retrieve the data you requested.",
                query_type="database",
                context_text=current_prompt,
                context_history=current_context_history,
                discovery_branch=discovery_branch if not use_table_override else "table_override"
            )
```

**Step 3: Commit**

```bash
git add app/models/schemas.py app/services/generation_service.py
git commit -m "feat(response): add discovery_branch metadata to GenerateSQLResponse for observability"
```

---

## Task 6: Enhance Prompt Construction for KB-Direct Branch

When Branch 1.1.1 is taken, the knowledge base examples should be prominently featured in the prompt, and the "adjustments_needed" from the LLM assessment should be injected as guidance.

**Files:**
- Modify: `app/services/generation_service.py` (prompt construction section, around line 1718-1735)

**Step 1: Add KB-direct guidance to reference section**

Find the block that builds `sql_references` and `reference_text` (around lines 1718-1734). Replace it with:

```python
    # Stage 3: Build Reference Section (Complexity-Mapped Knowledge Base Examples)
    sql_references = []
    
    # If KB-direct branch, prioritize KB examples and include adjustment guidance
    kb_guidance = ""
    if discovery_branch == "kb_direct" and kb_assessment:
        adjustments = kb_assessment.get("adjustments_needed", [])
        if adjustments:
            kb_guidance = "\n### KB-INFORMED ADJUSTMENTS\nThe following adjustments should be applied to the reference SQL:\n"
            for adj in adjustments:
                kb_guidance += f"- {adj}\n"
            kb_guidance += "\nUse the reference SQL as your starting point and apply these adjustments.\n"
    
    # Map knowledge base examples to complexity level
    complexity_relevant_queries = []
    for sq in (context.similar_queries or []):
        if sq.get("sql", "").strip():
            sq_complexity = score_query_complexity(sq.get("question", ""))
            if sq_complexity == query_complexity or not complexity_relevant_queries:
                complexity_relevant_queries.append(sq)
    
    # Build numbered knowledge base examples
    for idx, sq in enumerate(complexity_relevant_queries[:3], start=1):
        sql_references.append(f"Question {idx}: {sq.get('question', 'N/A')}\nSQL:\n```sql\n{sq.get('sql')}\n```")

    reference_text = "\n\n".join(sql_references) if sql_references else "No previous examples available."
    reference_text += kb_guidance
```

**Step 2: Commit**

```bash
git add app/services/generation_service.py
git commit -m "feat(prompt): inject KB adjustment guidance for high-confidence knowledge base matches"
```

---

## Task 7: Integration Testing and Verification

**Files:**
- None modified (read-only verification)

**Step 1: Verify module imports**

Run: `python -c "from app.services.generation_service import generate_sql_for_request; print('OK')"`
Expected: `OK`

**Step 2: Verify all models parse**

Run: `python -c "from app.models.schemas import KBAssessment, GenerateSQLResponse; print(KBAssessment.model_fields.keys()); print('discovery_branch' in GenerateSQLResponse.model_fields)"`
Expected: Shows field names and `True`

**Step 3: Verify LLM service interface**

Run: `python -c "from app.services.llm_service import LiteLLMService; print('evaluate_example_relevance' in dir(LiteLLMService))"`
Expected: `True`

**Step 4: Verify vector store interface**

Run: `python -c "from app.services.vector_store import MilvusVectorStore; print('search_fewshots_with_threshold' in dir(MilvusVectorStore))"`
Expected: `True`

**Step 5: Run existing tests (if any)**

Run: `python -m pytest tests/ -v --timeout=60 2>&1 | head -50`
Expected: Existing tests should still pass (no breaking changes to public APIs)

**Step 6: Commit (if any test fixes needed)**

```bash
git add -A
git commit -m "fix: address test failures from KB-first discovery refactor"
```

---

## Summary of Changes

| File | Change | Lines Affected |
|------|--------|---------------|
| `app/models/schemas.py` | Add `KBAssessment` model, add `discovery_branch` to `GenerateSQLResponse` | ~570, ~153 |
| `app/services/llm_service.py` | Add abstract `evaluate_example_relevance()` + implementations for OpenAI and LiteLLM | ~43, ~200, ~1337 |
| `app/services/vector_store.py` | Add `search_fewshots_with_threshold()` | ~564 |
| `app/services/generation_service.py` | Replace inline discovery block (1491-1534) with KB-first logic; add branch-aware validation routing; enhance prompt construction | ~1491-1712, ~1718-1734 |

## Performance Impact

| Branch | Expected Latency vs. Current | LLM Calls | Reasoning |
|--------|------------------------------|-----------|-----------|
| 1.1.1 (KB direct) | **-40% to -60% faster** | 2 (extract_entities + evaluate_example) vs. 4-5 current | Skips NER extraction, value search, schema completeness, sufficiency check |
| 1.1.2 (KB gap fill) | **-10% to +10%** (roughly equal) | 3-4 (evaluate + extract_tables + targeted search + sufficiency) | Skips Steps 8-9 but adds evaluate_example call |
| 1.2 (dual prong) | **+5% to +15% slower** | Same as current + 1 (threshold KB search adds ~0.3s) | Extra fewshot search at start; identical fallback path |

## Rollback Plan

If issues are detected, the refactor can be rolled back by:
1. Reverting the discovery block in `generation_service.py` to the original 6-step sequential flow
2. The new methods (`evaluate_example_relevance`, `search_fewshots_with_threshold`) can remain as they don't affect existing functionality
3. The `KBAssessment` model and `discovery_branch` field are additive (no breaking changes)
